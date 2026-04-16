"""Trading resume reconciliation service.

Ensures local task state is aligned with broker state before resuming an
orphaned live trading execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any, TypeVar

from django.utils import timezone as dj_timezone

from apps.market.services.oanda import OandaAPIError, OandaService, OrderDirection
from apps.trading.enums import Direction, TaskType
from apps.trading.models import Position, TradingTask
from apps.trading.models.state import ExecutionState

logger: Logger = getLogger(name=__name__)

_T = TypeVar("_T")

_OANDA_MAX_RETRIES = 3
_OANDA_RETRY_DELAY = 2.0  # seconds


def _oanda_call_with_retry(
    fn: Any,
    *args: Any,
    label: str = "OANDA API call",
    **kwargs: Any,
) -> Any:
    """Call an OANDA service method with retry on transient errors."""
    last_exc: OandaAPIError | None = None
    for attempt in range(1, _OANDA_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except OandaAPIError as exc:
            last_exc = exc
            if attempt < _OANDA_MAX_RETRIES:
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                    label,
                    attempt,
                    _OANDA_MAX_RETRIES,
                    exc,
                    _OANDA_RETRY_DELAY,
                )
                time.sleep(_OANDA_RETRY_DELAY)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    label,
                    _OANDA_MAX_RETRIES,
                    exc,
                )
    raise RuntimeError(
        f"{label} failed after {_OANDA_MAX_RETRIES} retries: {last_exc}"
    ) from last_exc


class TradingSafetyError(RuntimeError):
    """Raised when broker state is unsafe for automatic trading continuation."""


@dataclass(slots=True)
class ReconciliationReport:
    """Summary of broker/local state reconciliation."""

    updated_account_snapshot: bool = False
    broker_open_positions: int = 0
    pending_broker_orders: int = 0
    closed_local_positions: int = 0
    created_local_positions: int = 0
    updated_local_positions: int = 0
    removed_open_entries: int = 0
    synthesized_open_entries: int = 0
    relinked_open_entries: int = 0
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return bool(self.blockers)


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
    ) -> None:
        self.task = task
        self.state = state
        self.execution_id = task.execution_id
        self.oanda_service = OandaService(account=task.oanda_account, dry_run=False)

    def reconcile(self, *, resumed: bool) -> ReconciliationReport:
        """Run full reconciliation and return a summary report."""
        report = ReconciliationReport()
        self._sync_account_snapshot(report)
        self._check_pending_orders(report)
        open_positions = self._sync_positions_with_broker(report)
        self._sync_strategy_state_with_positions(open_positions, report)
        self._validate_safety(report=report, resumed=resumed)
        self._record_reconciliation_metadata(report=report)
        self.state.save()
        return report

    def detect_runtime_drift(self) -> ReconciliationReport:
        """Detect broker/local drift without mutating local state.

        This is used while a live trading task is actively running. Any mismatch
        is treated as unsafe because continuing would make strategy decisions on
        stale broker exposure.
        """
        report = ReconciliationReport()
        self._check_pending_orders(report)

        broker_trades = _oanda_call_with_retry(
            self.oanda_service.get_open_trades,
            instrument=self.task.instrument,
            label="Fetch open trades (drift check)",
        )
        report.broker_open_positions = len(broker_trades)

        local_open_positions = list(
            Position.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_id=self.execution_id,
                instrument=self.task.instrument,
                is_open=True,
            ).order_by("entry_time", "created_at")
        )
        if any(not position.oanda_trade_id for position in local_open_positions):
            report.blockers.append(
                "Found local open position(s) without OANDA trade ids while live trading is "
                "running. Broker drift detection cannot verify exposure safely."
            )

        broker_by_trade_id = {trade.trade_id: trade for trade in broker_trades if trade.trade_id}
        local_by_trade_id = {
            str(position.oanda_trade_id): position
            for position in local_open_positions
            if position.oanda_trade_id
        }

        for trade_id, local_position in local_by_trade_id.items():
            broker_trade = broker_by_trade_id.get(trade_id)
            if broker_trade is None:
                report.blockers.append(
                    f"OANDA trade {trade_id} for local position {local_position.pk} is no longer "
                    "open while the trading task is running."
                )
                continue

            broker_direction = (
                Direction.LONG if broker_trade.direction == OrderDirection.LONG else Direction.SHORT
            )
            broker_units = int(abs(broker_trade.units))
            local_units = int(abs(local_position.units))

            if local_position.direction != broker_direction:
                report.blockers.append(
                    f"OANDA trade {trade_id} direction changed from local "
                    f"{local_position.direction} to broker {broker_direction.value} while the "
                    "trading task is running."
                )

            if local_units != broker_units:
                report.blockers.append(
                    f"OANDA trade {trade_id} units changed from local {local_units} to broker "
                    f"{broker_units} while the trading task is running."
                )

        for trade_id, broker_trade in broker_by_trade_id.items():
            if trade_id in local_by_trade_id:
                continue
            report.blockers.append(
                f"OANDA trade {trade_id} for {broker_trade.instrument} is open at the broker "
                "but is not tracked locally while the trading task is running."
            )

        return report

    def _sync_account_snapshot(self, report: ReconciliationReport) -> None:
        details = _oanda_call_with_retry(
            self.oanda_service.get_account_details,
            label="Fetch account snapshot",
        )

        account = self.task.oanda_account
        account.currency = details.currency
        account.balance = details.balance
        account.margin_used = details.margin_used
        account.margin_available = details.margin_available
        account.unrealized_pnl = details.unrealized_pl
        account.save(
            update_fields=[
                "currency",
                "balance",
                "margin_used",
                "margin_available",
                "unrealized_pnl",
                "updated_at",
            ]
        )

        self.state.current_balance = details.balance
        report.updated_account_snapshot = True

    def _check_pending_orders(self, report: ReconciliationReport) -> None:
        pending_orders = _oanda_call_with_retry(
            self.oanda_service.get_pending_orders,
            instrument=self.task.instrument,
            label="Fetch pending orders",
        )

        report.pending_broker_orders = len(pending_orders)
        if pending_orders:
            report.blockers.append(
                f"OANDA account has {len(pending_orders)} pending order(s) for "
                f"{self.task.instrument}. Automatic trading is blocked until the "
                "account is reconciled manually."
            )

    def _sync_positions_with_broker(self, report: ReconciliationReport) -> list[Position]:
        broker_trades = _oanda_call_with_retry(
            self.oanda_service.get_open_trades,
            instrument=self.task.instrument,
            label="Fetch open trades (position sync)",
        )
        report.broker_open_positions = len(broker_trades)

        local_open_positions = list(
            Position.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_id=self.execution_id,
                instrument=self.task.instrument,
                is_open=True,
            ).order_by("entry_time", "created_at")
        )
        if any(not position.oanda_trade_id for position in local_open_positions):
            report.blockers.append(
                "Found local open position(s) without OANDA trade ids. Automatic resume "
                "cannot safely reconcile broker exposure."
            )

        broker_by_trade_id = {trade.trade_id: trade for trade in broker_trades if trade.trade_id}
        local_by_trade_id = {
            str(position.oanda_trade_id): position
            for position in local_open_positions
            if position.oanda_trade_id
        }

        for trade_id, local_position in local_by_trade_id.items():
            broker_trade = broker_by_trade_id.get(trade_id)
            if broker_trade is None:
                report.closed_local_positions += 1
                report.blockers.append(
                    f"OANDA trade {trade_id} for local position {local_position.pk} is no longer "
                    "open. Automatic close reconciliation is blocked to avoid losing "
                    "realized PnL or strategy state."
                )
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
                report.warnings.append(
                    f"Updated local position {local_position.pk} to match OANDA trade {trade_id}."
                )

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
                execution_id=self.execution_id,
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
            report.warnings.append(
                f"Created a missing local position for OANDA trade {trade_id} during reconciliation."
            )

        refreshed_open_positions = list(
            Position.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.task.pk,
                execution_id=self.execution_id,
                instrument=self.task.instrument,
                is_open=True,
            ).order_by("entry_time", "created_at")
        )

        return refreshed_open_positions

    def _validate_safety(self, *, report: ReconciliationReport, resumed: bool) -> None:
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()
        strategy_state = (
            self.state.strategy_state if isinstance(self.state.strategy_state, dict) else {}
        )

        if not resumed:
            if report.broker_open_positions > 0:
                report.warnings.append(
                    f"OANDA account has {report.broker_open_positions} existing open trade(s) for "
                    f"{self.task.instrument}. Fresh start will adopt the broker exposure into the "
                    "new execution instead of blocking the restart."
                )
            return

        # Block unsupported strategy types that had broker-side changes.
        if strategy_type not in {"snowball"} and (
            report.created_local_positions > 0
            or report.updated_local_positions > 0
            or report.closed_local_positions > 0
        ):
            report.blockers.append(
                "Automatic broker reconciliation is only state-aware for the snowball strategy. "
                f"Task strategy '{strategy_type or 'unknown'}' requires manual review before resume."
            )

        # Positions disappeared from the broker while the task was stopped.
        # The strategy cannot safely continue without them.
        if report.closed_local_positions > 0 or report.removed_open_entries > 0:
            report.blockers.append(
                "Broker exposure changed while the task was stopped. "
                f"{report.closed_local_positions} local position(s) were closed and "
                f"{report.removed_open_entries} strategy entry/entries could not be matched. "
                "Use restart to begin a fresh execution."
            )

        if report.broker_open_positions > 0 and not strategy_state:
            report.blockers.append(
                "Broker open trades exist but no persisted strategy state was found for this "
                "execution. Automatic resume is unsafe."
            )

    def _record_reconciliation_metadata(self, *, report: ReconciliationReport) -> None:
        unrealized_total = sum(
            (
                _safe_decimal(position.unrealized_pnl)
                for position in Position.objects.filter(
                    task_type=TaskType.TRADING,
                    task_id=self.task.pk,
                    execution_id=self.execution_id,
                    instrument=self.task.instrument,
                    is_open=True,
                )
            ),
            Decimal("0"),
        )
        strategy_state = (
            self.state.strategy_state if isinstance(self.state.strategy_state, dict) else {}
        )
        strategy_state["broker_reconciled_at"] = dj_timezone.now().isoformat()
        strategy_state["broker_unrealized_pnl"] = str(unrealized_total)
        strategy_state["broker_open_trade_count"] = report.broker_open_positions
        strategy_state["broker_pending_order_count"] = report.pending_broker_orders
        if report.warnings:
            strategy_state["broker_reconciliation_warnings"] = report.warnings
        if report.blockers:
            strategy_state["broker_reconciliation_blockers"] = report.blockers
        self.state.strategy_state = strategy_state

    def _sync_strategy_state_with_positions(
        self,
        open_positions: list[Position],
        report: ReconciliationReport,
    ) -> None:
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()

        if strategy_type == "snowball":
            self._sync_snowball_state_with_positions(open_positions, report)
            return

    def _sync_snowball_state_with_positions(
        self,
        open_positions: list[Position],
        report: ReconciliationReport,
    ) -> None:
        """Reconcile persisted snowball entries against open positions."""

        from apps.trading.strategies.snowball.models import SnowballStrategyState

        snowball_state = SnowballStrategyState.from_strategy_state(self.state.strategy_state)
        by_id = {str(position.id): position for position in open_positions}
        assigned_ids: set[str] = set()

        for cycle in snowball_state.cycles:
            for layer in cycle.grid.layers:
                for slot in layer.slots:
                    entry = slot.entry
                    if entry is None:
                        continue

                    matched = self._match_position_for_snowball_entry(
                        entry=entry,
                        open_positions=open_positions,
                        by_id=by_id,
                        assigned_ids=assigned_ids,
                    )
                    if matched is None:
                        report.removed_open_entries += 1
                        report.blockers.append(
                            f"Snowball entry {entry.entry_id} "
                            f"(L{entry.layer_number}/R{entry.retracement_count}) "
                            "has no matching broker position. "
                            "The position may have been closed externally while "
                            "the task was stopped. Use restart to begin a fresh execution."
                        )
                        continue

                    self._apply_position_to_snowball_entry(
                        entry=entry,
                        position=matched,
                        report=report,
                    )
                    assigned_ids.add(str(matched.id))

            for entry in cycle.hedge_entries:
                matched = self._match_position_for_snowball_entry(
                    entry=entry,
                    open_positions=open_positions,
                    by_id=by_id,
                    assigned_ids=assigned_ids,
                )
                if matched is None:
                    report.removed_open_entries += 1
                    report.blockers.append(
                        f"Snowball hedge entry {entry.entry_id} "
                        "has no matching broker position. "
                        "The position may have been closed externally while "
                        "the task was stopped. Use restart to begin a fresh execution."
                    )
                    continue

                self._apply_position_to_snowball_entry(
                    entry=entry,
                    position=matched,
                    report=report,
                )
                assigned_ids.add(str(matched.id))

        unmatched_positions = [
            position for position in open_positions if str(position.id) not in assigned_ids
        ]
        for position in unmatched_positions:
            report.synthesized_open_entries += 1
            report.blockers.append(
                "Snowball strategy state could not match open position "
                f"{position.id} (layer={position.layer_index}, retracement={position.retracement_count})."
            )

        snowball_state.account_balance = _safe_decimal(self.state.current_balance)
        snowball_state.account_nav = snowball_state.account_balance + sum(
            (_safe_decimal(position.unrealized_pnl) for position in open_positions),
            Decimal("0"),
        )
        self.state.strategy_state = snowball_state.to_dict()

    @staticmethod
    def _apply_position_to_snowball_entry(
        *,
        entry: Any,
        position: Position,
        report: ReconciliationReport,
    ) -> None:
        """Apply reconciled position fields back onto a persisted snowball entry."""

        position_id = str(position.id)
        if entry.position_id != position_id:
            entry.position_id = position_id
            report.relinked_open_entries += 1

        entry.direction = Direction(str(position.direction).lower())
        entry.units = abs(int(position.units))
        entry.entry_price = _safe_decimal(position.entry_price)
        entry.layer_number = int(position.layer_index or entry.layer_number or 1)
        entry.retracement_count = int(position.retracement_count or entry.retracement_count or 0)
        if position.entry_time is not None:
            entry.opened_at = position.entry_time

    @staticmethod
    def _match_position_for_snowball_entry(
        *,
        entry: Any,
        open_positions: list[Position],
        by_id: dict[str, Position],
        assigned_ids: set[str],
    ) -> Position | None:
        """Best-effort match between a persisted snowball entry and an open position."""

        position_id = str(getattr(entry, "position_id", "") or "").strip()
        if position_id:
            candidate = by_id.get(position_id)
            if candidate is not None and str(candidate.id) not in assigned_ids:
                return candidate

        entry_layer = int(getattr(entry, "layer_number", 0) or 0)
        entry_retracement = int(getattr(entry, "retracement_count", 0) or 0)
        entry_direction = str(getattr(entry, "direction", "") or "").lower()
        entry_units = abs(int(getattr(entry, "units", 0) or 0))
        entry_price = _safe_decimal(getattr(entry, "entry_price", None))

        best: Position | None = None
        best_price_diff: Decimal | None = None

        for candidate in open_positions:
            candidate_id = str(candidate.id)
            if candidate_id in assigned_ids:
                continue
            if entry_layer > 0 and int(candidate.layer_index or 0) != entry_layer:
                continue
            if int(candidate.retracement_count or 0) != entry_retracement:
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
