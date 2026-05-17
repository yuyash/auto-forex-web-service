"""Build editable initial-position cycles from existing tasks or OANDA."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.market.models import OandaAccounts
from apps.market.services.oanda import OandaService, OrderDirection
from apps.market.services.oanda_retry import OandaRetryPolicy
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTask, ExecutionState, StrategyConfiguration
from apps.trading.models import TradingTask
from apps.trading.services.backtest_initial_positions import (
    POSITION_STATUS_CLOSED_SLOT,
    POSITION_STATUS_OPEN,
    POSITION_STATUS_PENDING_REBUILD,
)
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState
from apps.trading.strategies.snowball.entries import Entry, StopLossClosedEntry
from apps.trading.strategies.snowball.parameters import SNOWBALL_PARAMETER_SERVICE

IMPORTABLE_TASK_STATUSES = {
    TaskStatus.STOPPED,
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.IDLE,
    TaskStatus.PAUSED,
}


class InitialPositionImportError(ValueError):
    """Raised when an initial-position import request is not valid."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.public_message = message
        self.code = code


@dataclass(frozen=True, slots=True)
class ImportMode:
    include_open: bool
    include_pending: bool


def import_mode_for_target(target_task_type: str) -> ImportMode:
    """Resolve which source position states may be imported for a target type."""
    if target_task_type == TaskType.TRADING.value:
        return ImportMode(include_open=False, include_pending=True)
    if target_task_type == TaskType.BACKTEST.value:
        return ImportMode(include_open=True, include_pending=True)
    raise InitialPositionImportError("Unsupported target task type.", code="unsupported_target")


class InitialPositionImportService:
    """Create initial-position cycle payloads for the task forms."""

    def list_sources(self, *, user: Any) -> list[dict[str, Any]]:
        """Return stopped/paused/idle terminal tasks that can be import sources."""
        rows: list[dict[str, Any]] = []
        for task_type, queryset in (
            (TaskType.BACKTEST, self._backtest_sources(user)),
            (TaskType.TRADING, self._trading_sources(user)),
        ):
            rows.extend(self._serialize_sources(task_type=task_type, queryset=queryset))
        rows.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return rows

    def import_from_task(
        self,
        *,
        user: Any,
        source_task_type: str,
        source_task_id: str,
        target_task_type: str,
    ) -> dict[str, Any]:
        """Build initial-position cycles from a task's active/pending Snowball state."""
        mode = import_mode_for_target(target_task_type)
        task_type = self._parse_task_type(source_task_type)
        task = self._get_source_task(
            user=user,
            task_type=task_type,
            source_task_id=source_task_id,
        )
        self._ensure_snowball_task(task)
        state = self._latest_state_for_task(task=task, task_type=task_type)
        if state is None:
            return self._result(
                cycles=[],
                source="task",
                imported_open=0,
                imported_pending=0,
                imported_closed_slots=0,
            )

        cycles = self._cycles_from_state(
            state=state,
            include_open=mode.include_open,
            include_pending=mode.include_pending,
        )
        imported_open, imported_pending, imported_closed_slots = _count_imported_positions(cycles)
        return self._result(
            cycles=cycles,
            source="task",
            imported_open=imported_open,
            imported_pending=imported_pending,
            imported_closed_slots=imported_closed_slots,
        )

    def import_from_oanda(
        self,
        *,
        user: Any,
        account_id: int,
        config_id: str,
        instrument: str,
    ) -> dict[str, Any]:
        """Build LONG/SHORT Snowball cycles from OANDA open trades."""
        account = self._get_account(user=user, account_id=account_id)
        config = self._get_config(user=user, config_id=config_id)
        self._ensure_snowball_config(config)
        normalized_instrument = str(instrument or "").strip().upper()
        if not normalized_instrument:
            raise InitialPositionImportError("Instrument is required.", code="instrument_required")

        client = OandaService(account=account, retry_policy=OandaRetryPolicy.short_default())
        trades = client.get_open_trades(instrument=normalized_instrument)
        cfg = SNOWBALL_PARAMETER_SERVICE.parse_config(config)
        by_direction: dict[str, list[Any]] = {"long": [], "short": []}
        for trade in trades:
            direction = "long" if trade.direction == OrderDirection.LONG else "short"
            by_direction[direction].append(trade)

        cycles: list[dict[str, Any]] = []
        for direction, direction_trades in by_direction.items():
            if not direction_trades:
                continue
            ordered = sorted(
                direction_trades,
                key=lambda trade: (trade.open_time is None, trade.open_time, trade.trade_id),
            )
            positions = [
                self._position_from_oanda_trade(
                    trade=trade,
                    index=index,
                    r_max=cfg.r_max,
                )
                for index, trade in enumerate(ordered)
            ]
            cycles.append({"direction": direction, "positions": positions})

        imported_open, imported_pending, imported_closed_slots = _count_imported_positions(cycles)
        return self._result(
            cycles=cycles,
            source="oanda",
            imported_open=imported_open,
            imported_pending=imported_pending,
            imported_closed_slots=imported_closed_slots,
        )

    def _backtest_sources(self, user: Any) -> QuerySet[BacktestTask]:
        return (
            BacktestTask.objects.filter(
                user=user,
                status__in=IMPORTABLE_TASK_STATUSES,
                config__strategy_type="snowball",
            )
            .select_related("config")
            .order_by("-updated_at")
        )

    def _trading_sources(self, user: Any) -> QuerySet[TradingTask]:
        return (
            TradingTask.objects.filter(
                user=user,
                status__in=IMPORTABLE_TASK_STATUSES,
                config__strategy_type="snowball",
            )
            .select_related("config", "oanda_account")
            .order_by("-updated_at")
        )

    def _serialize_sources(
        self,
        *,
        task_type: TaskType,
        queryset: QuerySet[BacktestTask] | QuerySet[TradingTask],
    ) -> list[dict[str, Any]]:
        return [
            {
                "task_type": task_type.value,
                "id": str(task.pk),
                "name": task.name,
                "status": task.status,
                "instrument": task.instrument,
                "config_id": str(task.config.pk),
                "config_name": task.config.name,
                "strategy_type": task.config.strategy_type,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in queryset
        ]

    def _parse_task_type(self, raw: str) -> TaskType:
        try:
            return TaskType(str(raw).strip().lower())
        except ValueError as exc:
            raise InitialPositionImportError(
                "Unsupported source task type.",
                code="unsupported_source",
            ) from exc

    def _get_source_task(
        self,
        *,
        user: Any,
        task_type: TaskType,
        source_task_id: str,
    ) -> BacktestTask | TradingTask:
        try:
            task_uuid = UUID(str(source_task_id))
        except ValueError as exc:
            raise InitialPositionImportError(
                "Source task id is invalid.",
                code="invalid_source_task",
            ) from exc

        model = BacktestTask if task_type == TaskType.BACKTEST else TradingTask
        try:
            return model.objects.select_related("config").get(
                user=user,
                pk=task_uuid,
                status__in=IMPORTABLE_TASK_STATUSES,
            )
        except model.DoesNotExist as exc:
            raise InitialPositionImportError(
                "Source task is not available for import.",
                code="source_task_not_found",
            ) from exc

    def _latest_state_for_task(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: TaskType,
    ) -> ExecutionState | None:
        queryset = ExecutionState.objects.filter(task_type=task_type.value, task_id=task.pk)
        if task.execution_id:
            state = queryset.filter(execution_id=task.execution_id).first()
            if state is not None:
                return state
        return queryset.order_by("-updated_at").first()

    def _cycles_from_state(
        self,
        *,
        state: ExecutionState,
        include_open: bool,
        include_pending: bool,
    ) -> list[dict[str, Any]]:
        try:
            snowball_state = SnowballStrategyState.from_strategy_state(state.strategy_state)
        except Exception as exc:
            raise InitialPositionImportError(
                "Source task does not have importable Snowball state.",
                code="source_state_not_importable",
            ) from exc

        cycles: list[dict[str, Any]] = []
        for cycle in sorted(snowball_state.cycles, key=_cycle_import_sort_key):
            if cycle.completed:
                continue
            has_importable_position = any(
                (include_open and slot.entry is not None)
                or (include_pending and slot.pending_rebuild is not None)
                for layer in cycle.layers
                for slot in layer.slots
            )
            if not has_importable_position:
                continue
            positions: list[dict[str, Any]] = []
            for layer in sorted(cycle.layers, key=lambda item: item.layer_number):
                for slot in sorted(layer.slots, key=lambda item: item.index):
                    if include_open and slot.entry is not None:
                        positions.append(_position_from_entry(slot.entry))
                    elif include_pending and slot.pending_rebuild is not None:
                        positions.append(_position_from_pending(slot.pending_rebuild))
                    elif slot.entry is None and slot.pending_rebuild is None and slot.ever_closed:
                        positions.append(_position_from_closed_slot(layer.layer_number, slot.index))
            if positions:
                positions.sort(
                    key=lambda item: (
                        int(item["layer_number"]),
                        int(item["retracement_count"]),
                    )
                )
                cycles.append({"direction": cycle.direction.value, "positions": positions})
        return cycles

    def _position_from_oanda_trade(
        self,
        *,
        trade: Any,
        index: int,
        r_max: int,
    ) -> dict[str, Any]:
        per_layer = r_max + 1
        layer_number = index // per_layer + 1
        retracement_count = index % per_layer
        return {
            "layer_number": layer_number,
            "retracement_count": retracement_count,
            "units": str(int(abs(Decimal(str(trade.units))))),
            "entry_price": str(trade.entry_price),
            "status": POSITION_STATUS_OPEN,
            "oanda_trade_id": str(trade.trade_id),
        }

    def _get_account(self, *, user: Any, account_id: int) -> OandaAccounts:
        try:
            return OandaAccounts.objects.get(pk=account_id, user=user, is_active=True)
        except OandaAccounts.DoesNotExist as exc:
            raise InitialPositionImportError(
                "OANDA account is not available.",
                code="account_not_found",
            ) from exc

    def _get_config(self, *, user: Any, config_id: str) -> StrategyConfiguration:
        try:
            return StrategyConfiguration.objects.get(pk=config_id, user=user)
        except (StrategyConfiguration.DoesNotExist, ValueError) as exc:
            raise InitialPositionImportError(
                "Strategy configuration is not available.",
                code="config_not_found",
            ) from exc

    def _ensure_snowball_task(self, task: BacktestTask | TradingTask) -> None:
        self._ensure_snowball_config(task.config)

    def _ensure_snowball_config(self, config: StrategyConfiguration) -> None:
        if str(config.strategy_type).strip().lower() != "snowball":
            raise InitialPositionImportError(
                "Initial-position import is supported only for Snowball tasks.",
                code="unsupported_strategy",
            )

    def _result(
        self,
        *,
        cycles: list[dict[str, Any]],
        source: str,
        imported_open: int,
        imported_pending: int,
        imported_closed_slots: int,
    ) -> dict[str, Any]:
        return {
            "cycles": cycles,
            "source": source,
            "summary": {
                "cycles": len(cycles),
                "positions": imported_open + imported_pending + imported_closed_slots,
                "open": imported_open,
                "pending": imported_pending,
                "closed_slots": imported_closed_slots,
            },
        }


def _position_from_entry(entry: Entry) -> dict[str, Any]:
    payload = {
        "layer_number": entry.layer_number,
        "retracement_count": entry.retracement_count,
        "units": str(abs(int(entry.units))),
        "entry_price": str(entry.entry_price),
        "planned_exit_price": str(entry.close_price),
        "status": POSITION_STATUS_OPEN,
    }
    if entry.stop_loss_price is not None:
        payload["stop_loss_price"] = str(entry.stop_loss_price)
    return payload


def _position_from_pending(pending: StopLossClosedEntry) -> dict[str, Any]:
    payload = {
        "layer_number": pending.layer_number,
        "retracement_count": pending.retracement_count,
        "units": str(abs(int(pending.units))),
        "entry_price": str(pending.entry_price),
        "planned_exit_price": str(pending.close_price),
        "status": POSITION_STATUS_PENDING_REBUILD,
        "close_reason": "stop_loss",
    }
    if pending.stop_loss_price is not None:
        payload["stop_loss_price"] = str(pending.stop_loss_price)
    if pending.stop_loss_exit_price is not None:
        payload["exit_price"] = str(pending.stop_loss_exit_price)
    return payload


def _position_from_closed_slot(layer_number: int, retracement_count: int) -> dict[str, Any]:
    return {
        "layer_number": layer_number,
        "retracement_count": retracement_count,
        "status": POSITION_STATUS_CLOSED_SLOT,
    }


def _count_imported_positions(cycles: list[dict[str, Any]]) -> tuple[int, int, int]:
    imported_open = 0
    imported_pending = 0
    imported_closed_slots = 0
    for cycle in cycles:
        for position in cycle.get("positions", []):
            if position.get("status") == POSITION_STATUS_PENDING_REBUILD:
                imported_pending += 1
            elif position.get("status") == POSITION_STATUS_CLOSED_SLOT:
                imported_closed_slots += 1
            else:
                imported_open += 1
    return imported_open, imported_pending, imported_closed_slots


def _cycle_import_sort_key(cycle: Any) -> int:
    return int(cycle.cycle_id)
