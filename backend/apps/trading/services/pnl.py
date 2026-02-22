"""PnL calculation service.

Computes Realized PnL, Unrealized PnL, and trade count for a given task
using efficient database aggregation queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Case, F, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade


@dataclass(frozen=True)
class PnlSummary:
    """Aggregated PnL summary for a task."""

    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_trades: int
    open_position_count: int


def compute_pnl_summary(
    task_type: str,
    task_id: str,
    celery_task_id: str | None = None,
) -> PnlSummary:
    """Compute PnL summary for a task using DB aggregation.

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
        PnlSummary with realized_pnl, unrealized_pnl, total_trades,
        and open_position_count.
    """
    base_filter = {"task_type": task_type, "task_id": task_id}
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

    # Total trade count
    trade_filter = {"task_type": task_type, "task_id": task_id}
    if celery_task_id:
        trade_filter["celery_task_id"] = celery_task_id
    total_trades = Trade.objects.filter(**trade_filter).count()

    return PnlSummary(
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_trades=total_trades,
        open_position_count=open_position_count,
    )


def _abs_units():
    """Return a DB expression for abs(units)."""
    return Case(
        When(units__lt=0, then=-F("units")),
        default=F("units"),
    )
