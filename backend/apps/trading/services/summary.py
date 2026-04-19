"""Task summary service.

Computes a comprehensive summary for a given task including:
- PnL (realized, unrealized)
- Trade / position counts
- Execution state (balance, ticks processed)
- Tick info (timestamp, bid, ask, mid)
- Task status and timing information
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade


@dataclass(frozen=True)
class TickInfo:
    """Last tick information."""

    timestamp: str | None
    bid: Decimal | None
    ask: Decimal | None
    mid: Decimal | None


@dataclass(frozen=True)
class PnlInfo:
    """Profit and loss information."""

    realized: Decimal
    unrealized: Decimal


@dataclass(frozen=True)
class CountsInfo:
    """Trade and position counts."""

    total_trades: int
    open_positions: int
    closed_positions: int
    open_long_units: int
    open_short_units: int
    winning_trades: int
    losing_trades: int


@dataclass(frozen=True)
class ExecutionInfo:
    """Execution state information."""

    current_balance: Decimal | None
    ticks_processed: int
    account_currency: str | None
    current_balance_display: Decimal | None
    display_currency: str | None
    margin_ratio: Decimal | None
    current_atr: Decimal | None


@dataclass(frozen=True)
class TaskInfo:
    """Task status information."""

    status: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    progress: int


@dataclass(frozen=True)
class TaskSummary:
    """Aggregated task summary with structured groups."""

    timestamp: str | None
    pnl: PnlInfo
    counts: CountsInfo
    execution: ExecutionInfo
    tick: TickInfo
    task: TaskInfo


def compute_task_summary(
    task_type: str,
    task_id: str,
    execution_id=None,
) -> TaskSummary:
    """Compute comprehensive task summary using DB aggregation.

    Realized PnL is calculated from closed positions:
      LONG:  (exit_price - entry_price) * abs(units)
      SHORT: (entry_price - exit_price) * abs(units)

    Unrealized PnL is the sum of open positions' unrealized_pnl field,
    which is updated each tick batch by the executor.

    Args:
        task_type: "backtest" or "trading".
        task_id: UUID of the task.
        execution_id: Optional execution UUID filter.

    Returns:
        TaskSummary with structured PnL, counts, execution, tick, and task info.
    """
    base_filter: dict = {"task_type": task_type, "task_id": task_id}
    if execution_id is not None:
        base_filter["execution_id"] = execution_id

    # Realized PnL + win/loss breakdown: aggregate over closed positions in
    # a single DB roundtrip.  The win/loss counts are what drives the
    # overview tab so they must come from the authoritative DB record,
    # not from the runtime counters (which we've seen drift to zero
    # after restarts that reuse the same execution_id).
    realized_agg = (
        Position.objects.filter(**base_filter, is_open=False)
        .exclude(exit_price__isnull=True)
        .annotate(
            _pnl_value=Case(
                When(
                    direction="long",
                    then=(F("exit_price") - F("entry_price")) * _abs_units(),
                ),
                When(
                    direction="short",
                    then=(F("entry_price") - F("exit_price")) * _abs_units(),
                ),
                default=Value(Decimal("0")),
                output_field=DecimalField(max_digits=24, decimal_places=10),
            )
        )
        .aggregate(
            realized_pnl=Sum("_pnl_value"),
            winning_trades=Sum(
                Case(
                    When(_pnl_value__gt=0, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            losing_trades=Sum(
                Case(
                    When(_pnl_value__lt=0, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        )
    )
    realized_pnl = realized_agg["realized_pnl"] or Decimal("0")
    winning_trades = int(realized_agg["winning_trades"] or 0)
    losing_trades = int(realized_agg["losing_trades"] or 0)

    # Unrealized PnL: sum of open positions' unrealized_pnl
    open_qs = Position.objects.filter(**base_filter, is_open=True)
    unrealized_agg = open_qs.aggregate(unrealized_pnl=Sum("unrealized_pnl"))
    unrealized_pnl = unrealized_agg["unrealized_pnl"] or Decimal("0")
    open_position_count = open_qs.count()
    open_size_agg = open_qs.aggregate(
        open_long_units=Sum(
            Case(
                When(direction="long", then=_abs_units()),
                default=Value(0),
                output_field=IntegerField(),
            )
        ),
        open_short_units=Sum(
            Case(
                When(direction="short", then=_abs_units()),
                default=Value(0),
                output_field=IntegerField(),
            )
        ),
    )

    # Closed position count
    closed_position_count = Position.objects.filter(**base_filter, is_open=False).count()

    # Total trade count
    trade_filter: dict = {"task_type": task_type, "task_id": task_id}
    if execution_id is not None:
        trade_filter["execution_id"] = execution_id
    total_trades = Trade.objects.filter(**trade_filter).count()

    # Execution state
    current_balance = None
    ticks_processed = 0
    tick_timestamp = None
    tick_bid = None
    tick_ask = None
    tick_mid = None
    account_currency: str | None = None
    current_balance_display: Decimal | None = None
    display_currency: str | None = None
    margin_ratio: Decimal | None = None
    current_atr: Decimal | None = None

    from apps.trading.models.state import ExecutionState

    state_filter: dict = {"task_type": task_type, "task_id": task_id}
    if execution_id is not None:
        state_filter["execution_id"] = execution_id
    state = ExecutionState.objects.filter(**state_filter).order_by("-updated_at").first()
    if state:
        current_balance = state.current_balance
        ticks_processed = state.ticks_processed
        if state.last_tick_timestamp:
            tick_timestamp = state.last_tick_timestamp.isoformat()
        tick_bid = state.last_tick_bid
        tick_ask = state.last_tick_ask
        tick_mid = state.last_tick_price

        # Extract margin_ratio and current_atr from strategy_state.metrics
        ss = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        metrics_dict = ss.get("metrics") if isinstance(ss.get("metrics"), dict) else {}
        if isinstance(metrics_dict, dict):
            raw_mr = metrics_dict.get("margin_ratio")
            if raw_mr is not None:
                try:
                    margin_ratio = Decimal(str(raw_mr))
                except (InvalidOperation, TypeError, ValueError):
                    pass  # nosec B110
            raw_atr = metrics_dict.get("current_atr")
            if raw_atr is not None:
                try:
                    current_atr = Decimal(str(raw_atr))
                except (InvalidOperation, TypeError, ValueError):
                    pass  # nosec B110

    # Task info
    status = ""
    started_at = None
    completed_at = None
    error_message = None

    task_obj = _get_task(task_type, task_id)
    if task_obj:
        status = task_obj.status
        started_at = task_obj.started_at.isoformat() if task_obj.started_at else None
        completed_at = task_obj.completed_at.isoformat() if task_obj.completed_at else None
        error_message = task_obj.error_message

    # Currency conversion for display
    if task_obj:
        if task_type == "backtest":
            account_currency = getattr(task_obj, "account_currency", None)
        else:
            account = getattr(task_obj, "oanda_account", None)
            account_currency = getattr(account, "currency", None)

    if task_obj and task_type == "backtest":
        instrument = getattr(task_obj, "instrument", "")
        quote_ccy = instrument.split("_")[-1].upper() if "_" in instrument else ""
        if (
            account_currency
            and quote_ccy
            and account_currency.upper() != quote_ccy
            and current_balance is not None
            and tick_mid is not None
            and tick_mid > 0
        ):
            display_currency = quote_ccy
            current_balance_display = current_balance * tick_mid
        elif account_currency and quote_ccy and account_currency.upper() == quote_ccy:
            # Account currency matches quote currency — no conversion needed
            display_currency = account_currency.upper()
            current_balance_display = current_balance

    return TaskSummary(
        timestamp=tick_timestamp,
        pnl=PnlInfo(realized=realized_pnl, unrealized=unrealized_pnl),
        counts=CountsInfo(
            total_trades=total_trades,
            open_positions=open_position_count,
            closed_positions=closed_position_count,
            open_long_units=int(open_size_agg["open_long_units"] or 0),
            open_short_units=int(open_size_agg["open_short_units"] or 0),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        ),
        execution=ExecutionInfo(
            current_balance=current_balance,
            ticks_processed=ticks_processed,
            account_currency=account_currency,
            current_balance_display=current_balance_display,
            display_currency=display_currency,
            margin_ratio=margin_ratio,
            current_atr=current_atr,
        ),
        tick=TickInfo(
            timestamp=tick_timestamp,
            bid=tick_bid,
            ask=tick_ask,
            mid=tick_mid,
        ),
        task=TaskInfo(
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error_message=error_message,
            progress=_compute_progress(task_type, task_obj, state),
        ),
    )


def compute_cached_task_summary(
    task_type: str,
    task_id: str,
    execution_id=None,
) -> TaskSummary:
    """Compute a cached task summary keyed by task/state freshness."""
    from apps.trading.services.execution_snapshots import get_summary_snapshot

    task_obj = _get_task(task_type, task_id)
    persisted_snapshot = get_summary_snapshot(
        task=task_obj,
        task_type=task_type,
        task_id=task_id,
        execution_id=str(execution_id) if execution_id is not None else None,
    )
    if persisted_snapshot is not None:
        return persisted_snapshot

    state = _get_state(task_type, task_id, execution_id)
    snapshot_cache_key = _build_task_summary_snapshot_cache_key(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        task_obj=task_obj,
    )
    if snapshot_cache_key:
        cached_snapshot = cache.get(snapshot_cache_key)
        if isinstance(cached_snapshot, TaskSummary):
            return cached_snapshot

    cache_key = _build_task_summary_cache_key(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        task_obj=task_obj,
        state=state,
    )
    cached = cache.get(cache_key)
    if isinstance(cached, TaskSummary):
        return cached

    summary = compute_task_summary(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    )
    cache.set(cache_key, summary, TASK_SUMMARY_CACHE_TTL_SECONDS)
    if snapshot_cache_key:
        cache.set(snapshot_cache_key, summary, TASK_SUMMARY_SNAPSHOT_CACHE_TTL_SECONDS)
    return summary


def _get_task(task_type: str, task_id: str):
    """Retrieve the task object by type and ID."""
    try:
        if task_type == "backtest":
            from apps.trading.models.backtest import BacktestTask

            return BacktestTask.objects.filter(pk=task_id).first()
        else:
            from apps.trading.models.trading import TradingTask

            return TradingTask.objects.filter(pk=task_id).first()
    except Exception:
        return None


def _get_state(task_type: str, task_id: str, execution_id=None):
    from apps.trading.models.state import ExecutionState

    state_filter: dict = {"task_type": task_type, "task_id": task_id}
    if execution_id is not None:
        state_filter["execution_id"] = execution_id
    return ExecutionState.objects.filter(**state_filter).order_by("-updated_at").first()


def _build_task_summary_cache_key(
    *, task_type: str, task_id: str, execution_id, task_obj, state
) -> str:
    task_updated_at = getattr(task_obj, "updated_at", None)
    task_updated_at_key = task_updated_at.isoformat() if task_updated_at else "na"
    state_updated_at = getattr(state, "updated_at", None)
    state_updated_at_key = state_updated_at.isoformat() if state_updated_at else "na"
    execution_key = str(execution_id or "latest")
    return (
        f"task-summary:{task_type}:{task_id}:{execution_key}:"
        f"{task_updated_at_key}:{state_updated_at_key}"
    )


def _build_task_summary_snapshot_cache_key(
    *, task_type: str, task_id: str, execution_id, task_obj
) -> str | None:
    if execution_id is None or not task_obj:
        return None
    current_execution_id = getattr(task_obj, "execution_id", None)
    if str(current_execution_id or "") != str(execution_id):
        return None
    if not _is_terminal_status(getattr(task_obj, "status", None)):
        return None
    return f"task-summary-snapshot:{task_type}:{task_id}:{execution_id}"


def _compute_progress(task_type: str, task_obj, state) -> int:
    """Compute progress percentage for a task.

    For backtest tasks, progress is calculated as:
      (last_tick_timestamp - start_time) / (end_time - start_time) * 100

    For trading tasks, progress is always 0 (no finite time range).

    Args:
        task_type: "backtest" or "trading".
        task_obj: The task model instance (or None).
        state: The ExecutionState instance (or None).

    Returns:
        int: Progress percentage (0-100).
    """
    if not task_obj:
        return 0

    if task_type != "backtest":
        return 0

    from apps.trading.enums import TaskStatus

    if task_obj.status == TaskStatus.COMPLETED:
        return 100
    if task_obj.status != TaskStatus.RUNNING:
        return 0

    if not state or not state.last_tick_timestamp:
        return 0

    try:
        total_duration = (task_obj.end_time - task_obj.start_time).total_seconds()
        if total_duration <= 0:
            return 0
        elapsed = (state.last_tick_timestamp - task_obj.start_time).total_seconds()
        progress = int((elapsed / total_duration) * 100)
        return max(0, min(progress, 99))
    except Exception:
        return 0


def _abs_units():
    """Return a DB expression for abs(units)."""
    return Case(
        When(units__lt=0, then=-F("units")),
        default=F("units"),
    )


TASK_SUMMARY_CACHE_TTL_SECONDS = 30
TASK_SUMMARY_SNAPSHOT_CACHE_TTL_SECONDS = 60 * 60 * 24


def _is_terminal_status(status: str | None) -> bool:
    return status in {"completed", "stopped", "failed"}
