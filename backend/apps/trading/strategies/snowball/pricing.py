"""Snowball price adjustment helpers."""

from __future__ import annotations

from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.calculators import rebuild_take_profit_pips
from apps.trading.strategies.snowball.models import (
    Layer,
    SnowballStrategyConfig,
    StopLossClosedEntry,
)


def rebuild_take_profit_price(
    *,
    pending: StopLossClosedEntry,
    entry_price: Decimal,
    pip_size: Decimal,
    config: SnowballStrategyConfig,
) -> Decimal:
    """Return the take-profit price for a rebuilt entry."""
    if config.rebuild_take_profit_mode == "same":
        return pending.close_price

    tp_pips = rebuild_take_profit_pips(pending.retracement_count + 1, config)
    if pending.direction == Direction.LONG:
        return entry_price + tp_pips * pip_size
    return entry_price - tp_pips * pip_size


def sync_weighted_average_counter_take_profits(layer: Layer) -> Decimal | None:
    """Recompute weighted-average TP and apply it to all live counters in a layer."""
    weighted = layer.current_weighted_avg_close_price()
    if weighted is None:
        return None

    close_price = weighted[0]
    for slot in layer.slots:
        if slot.entry is not None and slot.entry.role == "counter":
            slot.entry.close_price = close_price
    return close_price
