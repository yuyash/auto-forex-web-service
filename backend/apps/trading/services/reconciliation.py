"""Trading resume reconciliation service.

Ensures local task state is aligned with broker state before resuming an
orphaned live trading execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from django.utils import timezone as dj_timezone

from apps.market.services.oanda import OandaAPIError, OandaService, OrderDirection
from apps.trading.enums import Direction, TaskType
from apps.trading.models import Position, TradingTask
from apps.trading.models.state import ExecutionState

logger: Logger = getLogger(name=__name__)


@dataclass(slots=True)
class ReconciliationReport:
    """Summary of broker/local state reconciliation."""

    updated_account_snapshot: bool = False
    closed_local_positions: int = 0
    created_local_positions: int = 0
    updated_local_positions: int = 0
    removed_open_entries: int = 0
    synthesized_open_entries: int = 0
    relinked_open_entries: int = 0


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # nosec B110
        return Decimal(default)


class TradingResumeReconciler:
    """Reconcile broker and local state for live trading resume."""

    def __init__(
        self,
        *,
        task: TradingTask,
        state: ExecutionState,
        celery_task_id: str,
    ) -> None:
        self.task = task
        self.state = state
        self.celery_task_id = celery_task_id
        self.execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        self.oanda_service = OandaService(account=task.oanda_account, dry_run=False)

    def reconcile(self) -> ReconciliationReport:
        """Run full reconciliation and return a summary report."""
        report = ReconciliationReport()
        self._sync_account_snapshot(report)
        open_positions = self._sync_positions_with_broker(report)
        self._sync_strategy_state_with_positions(open_positions, report)
        self.state.save()
        return report

    def _sync_account_snapshot(self, report: ReconciliationReport) -> None:
        try:
            details = self.oanda_service.get_account_details()
        except OandaAPIError as exc:
            raise RuntimeError(f"Failed to fetch account snapshot from OANDA: {exc}") from exc

        account = self.task.oanda_account
        account.balance = details.balance
        account.margin_used = details.margin_used
        account.margin_available = details.margin_available
        account.unrealized_pnl = details.unrealized_pl
        account.save(
            update_fields=[
                "balance",
                "margin_used",
                "margin_available",
                "unrealized_pnl",
                "updated_at",
            ]
        )

        self.state.current_balance = details.balance
        report.updated_account_snapshot = True

    def _sync_positions_with_broker(self, report: ReconciliationReport) -> list[Position]:
        try:
            broker_trades = self.oanda_service.get_open_trades(instrument=self.task.instrument)
        except OandaAPIError as exc:
            raise RuntimeError(f"Failed to fetch open trades from OANDA: {exc}") from exc

        local_open_positions = list(
            Position.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_run_id=self.execution_run_id,
                instrument=self.task.instrument,
                is_open=True,
            ).order_by("entry_time", "created_at")
        )

        broker_by_trade_id = {trade.trade_id: trade for trade in broker_trades if trade.trade_id}
        local_by_trade_id = {
            str(position.oanda_trade_id): position
            for position in local_open_positions
            if position.oanda_trade_id
        }

        now = dj_timezone.now()
        for trade_id, local_position in local_by_trade_id.items():
            broker_trade = broker_by_trade_id.get(trade_id)
            if broker_trade is None:
                local_position.is_open = False
                local_position.exit_time = now
                local_position.exit_price = local_position.entry_price
                local_position.unrealized_pnl = Decimal("0")
                local_position.save(
                    update_fields=[
                        "is_open",
                        "exit_time",
                        "exit_price",
                        "unrealized_pnl",
                        "updated_at",
                    ]
                )
                report.closed_local_positions += 1
                continue

            updated_fields: list[str] = []
            expected_units = int(abs(broker_trade.units))
            signed_units = (
                expected_units if local_position.direction == Direction.LONG else -expected_units
            )
            if local_position.units != signed_units:
                local_position.units = signed_units
                updated_fields.append("units")

            if local_position.entry_price != broker_trade.entry_price:
                local_position.entry_price = broker_trade.entry_price
                updated_fields.append("entry_price")

            if local_position.unrealized_pnl != broker_trade.unrealized_pnl:
                local_position.unrealized_pnl = broker_trade.unrealized_pnl
                updated_fields.append("unrealized_pnl")

            if updated_fields:
                updated_fields.append("updated_at")
                local_position.save(update_fields=updated_fields)
                report.updated_local_positions += 1

        for trade_id, broker_trade in broker_by_trade_id.items():
            if trade_id in local_by_trade_id:
                continue

            direction = (
                Direction.LONG if broker_trade.direction == OrderDirection.LONG else Direction.SHORT
            )
            units_abs = int(abs(broker_trade.units))
            signed_units = units_abs if direction == Direction.LONG else -units_abs
            entry_time = broker_trade.open_time or dj_timezone.now()

            Position.objects.create(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_run_id=self.execution_run_id,
                celery_task_id=self.celery_task_id,
                instrument=broker_trade.instrument,
                direction=direction,
                units=signed_units,
                entry_price=broker_trade.entry_price,
                entry_time=entry_time,
                is_open=True,
                oanda_trade_id=broker_trade.trade_id,
                unrealized_pnl=broker_trade.unrealized_pnl,
            )
            report.created_local_positions += 1

        refreshed_open_positions = list(
            Position.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_run_id=self.execution_run_id,
                instrument=self.task.instrument,
                is_open=True,
            ).order_by("entry_time", "created_at")
        )

        unrealized_total = sum(
            (_safe_decimal(position.unrealized_pnl) for position in refreshed_open_positions),
            Decimal("0"),
        )
        strategy_state = (
            self.state.strategy_state if isinstance(self.state.strategy_state, dict) else {}
        )
        strategy_state["broker_reconciled_at"] = dj_timezone.now().isoformat()
        strategy_state["broker_unrealized_pnl"] = str(unrealized_total)
        self.state.strategy_state = strategy_state

        return refreshed_open_positions

    def _sync_strategy_state_with_positions(
        self,
        open_positions: list[Position],
        report: ReconciliationReport,
    ) -> None:
        if str(self.task.config.strategy_type) != "floor":
            return

        from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState

        floor_state = FloorStrategyState.from_strategy_state(self.state.strategy_state)
        floor_config = FloorStrategyConfig.from_dict(self.task.config.config_dict)

        by_id = {str(position.id): position for position in open_positions}
        assigned_ids: set[str] = set()
        next_entry_id = 1
        normalized_entries: list[dict[str, Any]] = []

        for raw_entry in floor_state.open_entries:
            if not isinstance(raw_entry, dict):
                continue

            entry = dict(raw_entry)
            entry_id = _safe_int(entry.get("entry_id"), 0)
            if entry_id > 0:
                next_entry_id = max(next_entry_id, entry_id + 1)

            matched = self._match_position_for_entry(
                entry=entry,
                open_positions=open_positions,
                by_id=by_id,
                assigned_ids=assigned_ids,
            )
            if matched is None:
                report.removed_open_entries += 1
                continue

            position_id = str(matched.id)
            if entry.get("position_id") != position_id:
                entry["position_id"] = position_id
                report.relinked_open_entries += 1

            entry["direction"] = str(matched.direction)
            entry["units"] = abs(int(matched.units))
            entry["entry_price"] = str(matched.entry_price)
            entry["floor_index"] = int(
                matched.layer_index or _safe_int(entry.get("floor_index"), 1)
            )
            entry["retracement_count"] = int(
                matched.retracement_count or _safe_int(entry.get("retracement_count"), 1) or 1
            )
            entry["opened_at"] = (
                matched.entry_time.isoformat()
                if matched.entry_time
                else str(entry.get("opened_at") or dj_timezone.now().isoformat())
            )
            entry["is_initial"] = bool(entry.get("is_initial", entry["retracement_count"] <= 1))
            normalized_entries.append(entry)
            assigned_ids.add(position_id)

        for position in open_positions:
            position_id = str(position.id)
            if position_id in assigned_ids:
                continue

            floor_index = int(position.layer_index or floor_state.active_floor_index or 1)
            retracement_count = int(position.retracement_count or 1)
            take_profit_pips = floor_config.intra_layer_take_profit_pips(
                floor_index,
                max(retracement_count - 1, 0),
            )
            normalized_entries.append(
                {
                    "entry_id": next_entry_id,
                    "floor_index": floor_index,
                    "direction": str(position.direction),
                    "entry_price": str(position.entry_price),
                    "units": abs(int(position.units)),
                    "take_profit_pips": str(take_profit_pips),
                    "opened_at": position.entry_time.isoformat(),
                    "is_initial": retracement_count <= 1,
                    "retracement_count": retracement_count,
                    "position_id": position_id,
                }
            )
            next_entry_id += 1
            report.synthesized_open_entries += 1

        floor_retracement_counts: dict[int, int] = {}
        floor_directions: dict[int, str] = {}
        max_floor = 1
        for entry in normalized_entries:
            floor_index = max(1, _safe_int(entry.get("floor_index"), 1))
            retracement_count = max(1, _safe_int(entry.get("retracement_count"), 1))
            direction = str(entry.get("direction", Direction.LONG)).lower()
            if direction not in {Direction.LONG, Direction.SHORT}:
                direction = Direction.LONG

            floor_retracement_counts[floor_index] = max(
                floor_retracement_counts.get(floor_index, 0),
                retracement_count,
            )
            floor_directions.setdefault(floor_index, direction)
            max_floor = max(max_floor, floor_index)

        floor_state.open_entries = normalized_entries
        floor_state.floor_retracement_counts = floor_retracement_counts
        floor_state.floor_directions = floor_directions
        floor_state.active_floor_index = max_floor if normalized_entries else 1
        floor_state.home_floor_index = min(
            max(1, floor_state.home_floor_index),
            floor_state.active_floor_index,
        )
        floor_state.next_entry_id = max(1, next_entry_id)
        floor_state.account_balance = _safe_decimal(self.state.current_balance)
        floor_state.account_nav = floor_state.account_balance + sum(
            (_safe_decimal(position.unrealized_pnl) for position in open_positions),
            Decimal("0"),
        )
        self.state.strategy_state = floor_state.to_dict()

    @staticmethod
    def _match_position_for_entry(
        *,
        entry: dict[str, Any],
        open_positions: list[Position],
        by_id: dict[str, Position],
        assigned_ids: set[str],
    ) -> Position | None:
        position_id = str(entry.get("position_id") or "").strip()
        if position_id:
            candidate = by_id.get(position_id)
            if candidate is not None:
                return candidate

        entry_floor = _safe_int(entry.get("floor_index"), 0)
        entry_direction = str(entry.get("direction") or "").lower()
        entry_units = _safe_int(entry.get("units"), 0)
        entry_price = _safe_decimal(entry.get("entry_price"), "0")

        best: Position | None = None
        best_price_diff: Decimal | None = None

        for candidate in open_positions:
            candidate_id = str(candidate.id)
            if candidate_id in assigned_ids:
                continue
            if entry_floor > 0 and int(candidate.layer_index or 0) != entry_floor:
                continue
            if (
                entry_direction in {Direction.LONG, Direction.SHORT}
                and str(candidate.direction) != entry_direction
            ):
                continue
            if entry_units > 0 and abs(int(candidate.units)) != entry_units:
                continue

            price_diff = abs(_safe_decimal(candidate.entry_price) - entry_price)
            if best is None or best_price_diff is None or price_diff < best_price_diff:
                best = candidate
                best_price_diff = price_diff

        return best
