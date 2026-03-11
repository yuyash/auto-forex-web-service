"""Unrealized PnL bulk-update service.

Called once per tick batch to update all open positions for a task
with their current unrealized PnL based on the latest market price.

Uses a single bulk UPDATE query to minimise DB round-trips.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, F, Value, When

from apps.trading.models.positions import Position


def update_unrealized_pnl(
    task_type: str,
    task_id: str,
    current_price: Decimal,
    execution_id=None,
) -> int:
    """Bulk-update unrealized_pnl for all open positions of a task.

    Formula:
      LONG:  (current_price - entry_price) * abs(units)
      SHORT: (entry_price - current_price) * abs(units)

    Args:
        task_type: "backtest" or "trading".
        task_id: UUID of the task.
        current_price: Latest mid price from the tick.
        execution_id: Optional execution UUID filter.

    Returns:
        Number of rows updated.
    """
    filters = {
        "task_type": task_type,
        "task_id": task_id,
        "is_open": True,
    }
    if execution_id is not None:
        filters["execution_id"] = execution_id

    abs_units = Case(
        When(units__lt=0, then=-F("units")),
        default=F("units"),
    )

    return Position.objects.filter(**filters).update(
        unrealized_pnl=Case(
            When(
                direction="long",
                then=(Value(current_price) - F("entry_price")) * abs_units,
            ),
            When(
                direction="short",
                then=(F("entry_price") - Value(current_price)) * abs_units,
            ),
            default=Value(Decimal("0")),
        )
    )
