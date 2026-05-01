"""Drain-on-stop and sell-on-stop coordination for task execution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from logging import Logger
from types import SimpleNamespace
from typing import Any, Protocol, cast

from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Position, TradingTask
from apps.trading.order import OrderServiceError
from apps.trading.services.drain import DrainCandidate, DrainPolicy


class DrainExecutor(Protocol):
    task: Any
    task_type: TaskType
    order_service: Any
    instrument: str
    logger: Logger
    _runtime_metrics: Any

    def _refresh_open_positions_cache(self) -> None: ...

    def _record_final_stop_metrics(self, loop: Any) -> None: ...


class TaskDrainCoordinator:
    """Coordinates drain-on-stop and stop-time position liquidation."""

    def __init__(self, executor: DrainExecutor) -> None:
        self.executor = executor

    def handle_pre_batch(self, loop: Any) -> bool:
        """Advance the drain state machine. Returns True when execution should stop."""
        executor = self.executor
        if executor.task_type != TaskType.TRADING:
            return False
        task = cast(TradingTask, executor.task)
        task.refresh_from_db(fields=["status"])
        if task.status != TaskStatus.DRAINING:
            return False

        drain_marker = self.read_drain_marker(loop)
        now = dj_timezone.now()
        if drain_marker is None:
            drain_marker = now
            self.record_drain_marker(loop, drain_marker)

        policy = DrainPolicy(
            drain_started_at=drain_marker,
            duration_hours=int(getattr(task, "drain_duration_hours", 0) or 0),
            duration_minutes=self.read_drain_duration_minutes_override(loop),
        )
        candidates = [
            DrainCandidate(
                position_id=str(position.pk),
                current_unrealized_pnl=_decimal_or_zero(getattr(position, "unrealized_pnl", None)),
            )
            for position in executor.order_service.get_open_positions(
                instrument=executor.instrument
            )
        ]
        decision = policy.evaluate(now=now, open_positions=candidates)

        for position_id in decision.close_position_ids:
            self.close_position_during_drain(position_id)

        if not decision.should_finalize:
            return False

        executor.logger.info(
            "Drain complete - task_id=%s, reason=%s",
            task.pk,
            decision.finalize_reason,
        )
        loop.stopped_early = True
        loop.stop_reason = decision.finalize_reason or "drain_complete"
        self.record_drain_marker(loop, None)
        self.clear_drain_duration_minutes_override(loop)
        return True

    def close_position_during_drain(self, position_id: str) -> None:
        """Close a single position; errors are logged and swallowed."""
        try:
            position = Position.objects.get(pk=position_id, is_open=True)
        except Position.DoesNotExist:  # pragma: no cover - race with close
            return
        try:
            self.executor.order_service.close_position(position=position)
        except OrderServiceError as exc:
            self.executor.logger.warning(
                "Drain close failed - position_id=%s, error=%s",
                position_id,
                exc,
            )

    def close_all_positions_on_stop_if_requested(self, loop: Any) -> None:
        """Close every open position when ``sell_on_stop`` was requested."""
        executor = self.executor
        executor.task.refresh_from_db(fields=["sell_on_stop"])
        if not getattr(executor.task, "sell_on_stop", False):
            return

        open_positions = executor.order_service.get_open_positions(instrument=executor.instrument)
        if not open_positions:
            executor.logger.info(
                "sell_on_stop requested but no open positions - task_id=%s",
                executor.task.pk,
            )
            return

        executor.logger.info(
            "Closing %d open position(s) on stop - task_id=%s",
            len(open_positions),
            executor.task.pk,
        )
        for position in open_positions:
            self._close_position_on_stop(loop, position)

        executor._refresh_open_positions_cache()
        executor._record_final_stop_metrics(loop)

    def record_drain_marker(self, loop: Any, started_at: datetime | None) -> None:
        strategy_state = _strategy_state(loop)
        if started_at is None:
            strategy_state.pop("_drain_started_at", None)
        else:
            strategy_state["_drain_started_at"] = started_at.isoformat()
        loop.state.strategy_state = strategy_state
        try:
            loop.state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:  # pragma: no cover
            self.executor.logger.debug("Failed to persist drain marker", exc_info=True)

    def read_drain_marker(self, loop: Any) -> datetime | None:
        raw = _strategy_state(loop).get("_drain_started_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    def read_drain_duration_minutes_override(self, loop: Any) -> int | None:
        raw = _strategy_state(loop).get("_drain_duration_minutes_override")
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def clear_drain_duration_minutes_override(self, loop: Any) -> None:
        strategy_state = _strategy_state(loop)
        if "_drain_duration_minutes_override" not in strategy_state:
            return
        strategy_state.pop("_drain_duration_minutes_override", None)
        loop.state.strategy_state = strategy_state
        try:
            loop.state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:  # pragma: no cover
            self.executor.logger.debug(
                "Failed to clear drain duration minutes override",
                exc_info=True,
            )

    def _close_position_on_stop(self, loop: Any, position: Any) -> None:
        executor = self.executor
        closed_units = abs(position.units)
        override_price = None
        tick_timestamp = None
        if executor.task_type == TaskType.BACKTEST:
            tick_timestamp = loop.state.last_tick_timestamp
            override_price = (
                loop.state.last_tick_bid
                if position.direction == "long"
                else loop.state.last_tick_ask
            )

        try:
            closed_position, realized_delta, _order = executor.order_service.close_position(
                position=position,
                override_price=(
                    Decimal(str(override_price)) if override_price is not None else None
                ),
                tick_timestamp=tick_timestamp,
            )
        except OrderServiceError as exc:
            executor.logger.warning(
                "sell_on_stop close failed - task_id=%s, position_id=%s, error=%s",
                executor.task.pk,
                getattr(position, "pk", None),
                exc,
            )
            return

        loop.state.current_balance = Decimal(str(loop.state.current_balance)) + realized_delta
        exit_px = closed_position.exit_price or (
            Decimal(str(override_price)) if override_price is not None else Decimal("0")
        )
        quote_delta = exit_px - Decimal(str(position.entry_price))
        if position.direction == "short":
            quote_delta = -quote_delta
        executor._runtime_metrics.record_position_closed(
            realized_delta,
            realized_pnl_quote=quote_delta * Decimal(str(closed_units)),
        )


def record_final_stop_metrics(executor: Any, loop: Any) -> None:
    """Refresh the final metrics snapshot after stop-time position closes."""
    if (
        loop.state.last_tick_timestamp is None
        or loop.state.last_tick_bid is None
        or loop.state.last_tick_ask is None
        or loop.state.last_tick_price is None
    ):
        return

    tick = SimpleNamespace(
        timestamp=loop.state.last_tick_timestamp,
        bid=loop.state.last_tick_bid,
        ask=loop.state.last_tick_ask,
        mid=loop.state.last_tick_price,
    )
    executor._update_common_metrics(loop.state, tick)
    executor._buffer_tick_metrics(loop.state, tick)


def _strategy_state(loop: Any) -> dict[str, Any]:
    return loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}


def _decimal_or_zero(value: Any) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0")
