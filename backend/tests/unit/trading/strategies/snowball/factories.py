"""Shared Snowball strategy test factories."""

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.entries import Entry

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def entry(
    entry_id: int = 1,
    direction: Direction = Direction.LONG,
    entry_price: str = "150.00",
    close_price: str = "150.50",
    units: int = 1000,
    role: str = "counter",
    layer_number: int = 1,
    retracement_count: int = 0,
) -> Entry:
    """Return a Snowball Entry with deterministic defaults."""
    return Entry(
        entry_id=entry_id,
        step=1,
        direction=direction,
        entry_price=Decimal(entry_price),
        close_price=Decimal(close_price),
        units=units,
        opened_at=T0,
        role=role,
        layer_number=layer_number,
        retracement_count=retracement_count,
    )
