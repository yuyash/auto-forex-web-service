"""Task summary service.

Computes a comprehensive summary for a given task including:
- Realized PnL, Unrealized PnL
- Trade / position counts
- Execution state (balance, ticks processed, last tick)
- Task status and timing information
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Case, F, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade


@dataclass(frozen=True)
class TaskSummary:
    """Aggregated task summary."""

    # PnL
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    # Counts
    total_trades: int
    open_position_count: int
    closed_position_count: int
    # Execution state
    current_balance: Decimal | None
    ticks_processed: int
    last_tick_time: str | None
    last_tick_price: Decimal | None
    # Task info
    status: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    # Progress (backtest only, 0-100)
    progress: int


def compute_task_summary(
    task_type: str,
    task_id: str,
    celery_task_id: str | None = None,
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
        celery_task_id: Optional celery task ID filter.

    Returns:
        TaskSummary with PnL, counts, execution state, and task info.
    """
    base_filter: dict = {"task_type": task_type, "task_id": task_id}
    if celery_task_id:
        base_filter["celery_task_id"] = celery_task_id

    # Realized PnL: aggregate over closed positions
    realized_agg = (
        Position.objects.filter(**base_filter, is_open=False)
        .exclude(exit_price__isnull=True)
        .aggregate(
            realized_pnl=Sum(
                Case(
                    When(
                        direction="long",
                        then=(F("exit_price") - F("entry_price")) * _abs_units(),
                    ),
                    When(
                        direction="short",
                        then=(F("entry_price") - F("exit_price")) * _abs_units(),
                    ),
                    default=Value(Decimal("0")),
                )
            )
        )
    )
    realized_pnl = realized_agg["realized_pnl"] or Decimal("0")

    # Unrealized PnL: sum of open positions' unrealized_pnl
    open_qs = Position.objects.filter(**base_filter, is_open=True)
    unrealized_agg = open_qs.aggregate(unrealized_pnl=Sum("unrealized_pnl"))
    unrealized_pnl = unrealized_agg["unrealized_pnl"] or Decimal("0")
    open_position_count = open_qs.count()

    # Closed position count
    closed_position_count = Position.objects.filter(**base_filter, is_open=False).count()

    # Total trade count
    trade_filter: dict = {"task_type": task_type, "task_id": task_id}
    if celery_task_id:
        trade_filter["celery_task_id"] = celery_task_id
    total_trades = Trade.objects.filter(**trade_filter).count()

    # Execution state
    current_balance = None
    ticks_processed = 0
    last_tick_time = None
    last_tick_price = None

    from apps.trading.models.state import ExecutionState

    state_filter: dict = {"task_type": task_type, "task_id": task_id}
    if celery_task_id:
        state_filter["celery_task_id"] = celery_task_id
    state = ExecutionState.objects.filter(**state_filter).order_by("-updated_at").first()
    if state:
        current_balance = state.current_balance
        ticks_processed = state.ticks_processed
        if state.last_tick_timestamp:
            last_tick_time = state.last_tick_timestamp.isoformat()
        last_tick_price = state.last_tick_price

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

    return TaskSummary(
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_trades=total_trades,
        open_position_count=open_position_count,
        closed_position_count=closed_position_count,
        current_balance=current_balance,
        ticks_processed=ticks_processed,
        last_tick_time=last_tick_time,
        last_tick_price=last_tick_price,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        error_message=error_message,
        progress=_compute_progress(task_type, task_obj, state),
    )


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
