"""Trading resume reconciliation service.

Ensures local task state is aligned with broker state before resuming an
orphaned live trading execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any, TypeVar

from django.db.models import F
from django.utils import timezone as dj_timezone

from apps.market.services.oanda import OandaService, OrderDirection, Transaction
from apps.trading.enums import Direction, TaskType
from apps.trading.models import Order, Position, Trade, TradingTask
from apps.trading.models.orders import OrderStatus, OrderType
from apps.trading.models.state import ExecutionState
from apps.trading.services.oanda_retry import OandaRetryPolicy, call_with_retry

logger: Logger = getLogger(name=__name__)

_T = TypeVar("_T")


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
    backfilled_broker_fills: int = 0
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


def _net_units_from_broker_trades(broker_trades: list[Any]) -> int:
    total = 0
    for trade in broker_trades:
        units = int(abs(getattr(trade, "units", 0) or 0))
        if getattr(trade, "direction", None) == OrderDirection.SHORT:
            units = -units
        total += units
    return total


def _weighted_average_from_broker_trades(broker_trades: list[Any]) -> Decimal | None:
    total_units = 0
    weighted = Decimal("0")
    for trade in broker_trades:
        units = int(abs(getattr(trade, "units", 0) or 0))
        if units <= 0:
            continue
        total_units += units
        weighted += Decimal(str(getattr(trade, "entry_price", "0"))) * Decimal(str(units))
    if total_units <= 0:
        return None
    return weighted / Decimal(str(total_units))


def _weighted_average_from_local_positions(positions: list[Position]) -> Decimal | None:
    total_units = 0
    weighted = Decimal("0")
    for position in positions:
        units = abs(int(position.units or 0))
        if units <= 0:
            continue
        total_units += units
        weighted += Decimal(str(position.entry_price)) * Decimal(str(units))
    if total_units <= 0:
        return None
    return weighted / Decimal(str(total_units))


class TradingResumeReconciler:
    """Reconcile broker and local state for live trading resume."""

    def __init__(
        self,
        *,
        task: TradingTask,
        state: ExecutionState,
        retry_policy: OandaRetryPolicy | None = None,
    ) -> None:
        self.task = task
        self.state = state
        self.execution_id = task.execution_id
        self.oanda_service = OandaService(account=task.oanda_account, dry_run=False)
        self.retry_policy = retry_policy or OandaRetryPolicy.from_task(task)

    def _oanda_call(
        self,
        fn: Any,
        *args: Any,
        label: str,
        **kwargs: Any,
    ) -> Any:
        """Call an OANDA service method with the task-scoped retry policy."""
        return call_with_retry(
            fn,
            *args,
            policy=self.retry_policy,
            label=label,
            **kwargs,
        )

    def reconcile(self, *, resumed: bool) -> ReconciliationReport:
        """Run full reconciliation and return a summary report."""
        report = ReconciliationReport()
        self._sync_account_snapshot(report)
        self._check_pending_orders(report)
        open_positions = self._sync_positions_with_broker(report)
        self._backfill_broker_fills(report)
        self._sync_strategy_state_with_positions(open_positions, report)
        self._validate_safety(report=report, resumed=resumed)
        self._record_reconciliation_metadata(report=report)
        self._persist_state()
        return report

    def detect_runtime_drift(self) -> ReconciliationReport:
        """Detect broker/local drift without mutating local state.

        This is used while a live trading task is actively running. Any mismatch
        is treated as unsafe because continuing would make strategy decisions on
        stale broker exposure.
        """
        report = ReconciliationReport()
        self._check_pending_orders(report)

        broker_trades = self._oanda_call(
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
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()
        if strategy_type == "net_grid":
            self._detect_net_grid_runtime_drift(
                broker_trades=broker_trades,
                local_open_positions=local_open_positions,
                report=report,
            )
            return report

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

    def _detect_net_grid_runtime_drift(
        self,
        *,
        broker_trades: list[Any],
        local_open_positions: list[Position],
        report: ReconciliationReport,
    ) -> None:
        broker_net = _net_units_from_broker_trades(broker_trades)
        local_net = sum((int(position.units or 0) for position in local_open_positions), 0)
        if broker_net != local_net:
            report.blockers.append(
                f"OANDA net exposure for {self.task.instrument} changed from local "
                f"{local_net} to broker {broker_net} while the Net Grid task is running."
            )
            return

        broker_avg = _weighted_average_from_broker_trades(broker_trades)
        local_avg = _weighted_average_from_local_positions(local_open_positions)
        if broker_avg is None and local_avg is None:
            return
        if broker_avg is None or local_avg is None:
            report.blockers.append(
                "OANDA and local Net Grid average entry state differ while the task is running."
            )
            return
        if abs(broker_avg - local_avg) > Decimal("0.0000001"):
            report.blockers.append(
                f"OANDA average entry for {self.task.instrument} changed from local "
                f"{local_avg} to broker {broker_avg} while the Net Grid task is running."
            )

    def _sync_account_snapshot(self, report: ReconciliationReport) -> None:
        details = self._oanda_call(
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
        pending_orders = self._oanda_call(
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
        broker_trades = self._oanda_call(
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

    def _backfill_broker_fills(self, report: ReconciliationReport) -> None:
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()
        if strategy_type != "net_grid":
            return

        strategy_state = (
            self.state.strategy_state if isinstance(self.state.strategy_state, dict) else {}
        )
        from_time = (
            self.state.last_tick_timestamp
            or getattr(self.state, "created_at", None)
            or getattr(self.task, "created_at", None)
        )
        last_backfilled_id = _safe_int(strategy_state.get("broker_last_backfilled_transaction_id"))
        transactions = self._oanda_call(
            self.oanda_service.get_transaction_history,
            from_time=from_time,
            transaction_type="ORDER_FILL",
            label="Fetch transaction history (net grid backfill)",
        )
        fills = [
            tx
            for tx in sorted(transactions, key=lambda item: int(item.transaction_id or "0"))
            if tx.type == "ORDER_FILL"
            and tx.instrument == self.task.instrument
            and tx.transaction_id
            and tx.units not in (None, Decimal("0"))
            and _safe_int(tx.transaction_id) > last_backfilled_id
            and not self._broker_fill_already_recorded(tx)
        ]
        if not fills:
            return

        for tx in fills:
            order = self._create_backfilled_order(tx)
            self._create_backfilled_trade(tx, order)
            self._append_backfill_ledger_entry(strategy_state, tx)
            report.backfilled_broker_fills += 1

        last_tx_id = fills[-1].transaction_id
        strategy_state["broker_last_backfilled_transaction_id"] = last_tx_id
        strategy_state["broker_backfilled_fill_count"] = int(
            strategy_state.get("broker_backfilled_fill_count", 0) or 0
        ) + len(fills)
        strategy_state["broker_backfilled_at"] = dj_timezone.now().isoformat()
        self.state.strategy_state = strategy_state
        report.warnings.append(
            f"Backfilled {len(fills)} OANDA fill transaction(s) into Net Grid local history."
        )

    def _broker_fill_already_recorded(self, tx: Transaction) -> bool:
        return Order.objects.filter(
            task_type=TaskType.TRADING,
            task_id=self.task.pk,
            execution_id=self.execution_id,
            broker_order_id=tx.transaction_id,
        ).exists()

    def _create_backfilled_order(self, tx: Transaction) -> Order:
        signed_units = int(tx.units or 0)
        direction = Direction.LONG if signed_units > 0 else Direction.SHORT
        order = Order.objects.create(
            task_type=TaskType.TRADING,
            task_id=self.task.pk,
            execution_id=self.execution_id,
            broker_order_id=tx.transaction_id,
            oanda_trade_id=tx.trade_id,
            instrument=self.task.instrument,
            order_type=OrderType.MARKET,
            direction=direction,
            units=signed_units,
            fill_price=tx.price,
            status=OrderStatus.FILLED,
            filled_at=tx.time or dj_timezone.now(),
            is_dry_run=False,
        )
        return order

    def _create_backfilled_trade(self, tx: Transaction, order: Order) -> Trade:
        signed_units = int(tx.units or 0)
        direction = Direction.LONG if signed_units > 0 else Direction.SHORT
        return Trade.objects.create(
            task_type=TaskType.TRADING.value,
            task_id=self.task.pk,
            execution_id=self.execution_id,
            timestamp=tx.time or dj_timezone.now(),
            direction=direction.value,
            units=abs(signed_units),
            instrument=self.task.instrument,
            price=tx.price or Decimal("0"),
            execution_method="broker_backfill",
            oanda_trade_id=tx.trade_id,
            order=order,
            description=(
                f"[BROKER BACKFILL] OANDA ORDER_FILL transaction {tx.transaction_id}"
                + (f" ({tx.reason})" if tx.reason else "")
            ),
        )

    def _append_backfill_ledger_entry(
        self,
        strategy_state: dict[str, Any],
        tx: Transaction,
    ) -> None:
        raw_ledger = strategy_state.get("grid_ledger")
        ledger: list[dict[str, Any]] = raw_ledger if isinstance(raw_ledger, list) else []
        before_net = _safe_int(strategy_state.get("current_net_units"))
        units_delta = int(tx.units or 0)
        after_net = before_net + units_delta
        entry = {
            "timestamp": tx.time.isoformat() if tx.time else None,
            "action": "broker_backfill",
            "reason": tx.reason or "order_fill",
            "units_delta": units_delta,
            "filled_price": str(tx.price) if tx.price is not None else None,
            "net_units_before": before_net,
            "net_units_after": after_net,
            "avg_price_before": strategy_state.get("average_entry_price"),
            "avg_price_after": strategy_state.get("average_entry_price"),
            "realized_pnl": str(tx.pl or "0"),
            "realized_pnl_quote": str(tx.pl or "0"),
            "source": "broker_transaction_history",
            "broker_transaction_id": tx.transaction_id,
            "broker_order_id": tx.order_id,
            "oanda_trade_id": tx.trade_id,
        }
        strategy_state["grid_ledger"] = [*ledger, entry][-500:]
        strategy_state["latest_position_transition"] = entry

    def _validate_safety(self, *, report: ReconciliationReport, resumed: bool) -> None:
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()
        strategy_state = (
            self.state.strategy_state if isinstance(self.state.strategy_state, dict) else {}
        )
        from apps.trading.strategies.registry import registry

        supports_stateful_reconciliation = registry.is_registered(
            strategy_type
        ) and registry.supports_stateful_broker_reconciliation(strategy_type)

        if not resumed:
            if report.broker_open_positions > 0:
                report.warnings.append(
                    f"OANDA account has {report.broker_open_positions} existing open trade(s) for "
                    f"{self.task.instrument}. Fresh start will adopt the broker exposure into the "
                    "new execution instead of blocking the restart."
                )
            return

        # Block unsupported strategy types that had broker-side changes.
        if not supports_stateful_reconciliation and (
            report.created_local_positions > 0
            or report.updated_local_positions > 0
            or report.closed_local_positions > 0
        ):
            report.blockers.append(
                "Automatic broker reconciliation is not state-aware for this strategy. "
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
        strategy_state["broker_reconciliation_status"] = (
            "blocked" if report.blockers else "warning" if report.warnings else "ok"
        )
        strategy_state["broker_unrealized_pnl"] = str(unrealized_total)
        strategy_state["broker_open_trade_count"] = report.broker_open_positions
        strategy_state["broker_pending_order_count"] = report.pending_broker_orders
        strategy_state["broker_backfilled_fill_count_latest"] = report.backfilled_broker_fills
        if report.warnings:
            strategy_state["broker_reconciliation_warnings"] = report.warnings
        if report.blockers:
            strategy_state["broker_reconciliation_blockers"] = report.blockers
        self.state.strategy_state = strategy_state

    def _persist_state(self) -> None:
        now = dj_timezone.now()
        rows = ExecutionState.objects.filter(
            pk=self.state.pk,
            state_version=self.state.state_version,
        ).update(
            strategy_state=self.state.strategy_state,
            current_balance=self.state.current_balance,
            ticks_processed=self.state.ticks_processed,
            last_tick_timestamp=self.state.last_tick_timestamp,
            resume_cursor_timestamp=(
                self.state.resume_cursor_timestamp or self.state.last_tick_timestamp
            ),
            last_tick_price=self.state.last_tick_price,
            last_tick_bid=self.state.last_tick_bid,
            last_tick_ask=self.state.last_tick_ask,
            updated_at=now,
            state_version=F("state_version") + 1,
        )
        if rows != 1:
            raise TradingSafetyError(
                "Execution state changed during broker reconciliation. Retry resume after refresh."
            )
        self.state.state_version += 1

    def _sync_strategy_state_with_positions(
        self,
        open_positions: list[Position],
        report: ReconciliationReport,
    ) -> None:
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "").strip().lower()

        from apps.trading.strategies.registry import registry

        if not registry.is_registered(strategy_type):
            return
        registry.reconcile_broker_positions(
            identifier=strategy_type,
            state=self.state,
            open_positions=open_positions,
            report=report,
            strategy_config=self.task.config,
        )
