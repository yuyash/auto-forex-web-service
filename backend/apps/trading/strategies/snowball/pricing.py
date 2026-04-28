"""Snowball price adjustment helpers."""

from __future__ import annotations

from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.calculators import rebuild_take_profit_pips
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
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
        price = pending.close_price
    else:
        tp_pips = rebuild_take_profit_pips(pending.retracement_count + 1, config)
        price = _take_profit_price(
            direction=pending.direction,
            entry_price=entry_price,
            tp_pips=tp_pips,
            pip_size=pip_size,
        )

    if not config.rebuild_take_profit_recovery_enabled:
        return price

    recovery_pips = pending.stop_loss_loss_pips
    if recovery_pips <= 0:
        return price

    recovery_price = _take_profit_price(
        direction=pending.direction,
        entry_price=entry_price,
        tp_pips=recovery_pips,
        pip_size=pip_size,
    )
    if pending.direction == Direction.LONG:
        return recovery_price if recovery_price > price else price
    return recovery_price if recovery_price < price else price


def _take_profit_price(
    *,
    direction: Direction,
    entry_price: Decimal,
    tp_pips: Decimal,
    pip_size: Decimal,
) -> Decimal:
    if direction == Direction.LONG:
        return entry_price + tp_pips * pip_size
    return entry_price - tp_pips * pip_size


def weighted_avg_close_price(
    layer: Layer,
    *,
    new_price: Decimal,
    new_units: int,
    include_ref: Entry | None = None,
) -> tuple[Decimal, str]:
    """Compute weighted-average close price for a new entry in a layer."""
    total_cost = new_price * Decimal(str(new_units))
    total_units = new_units
    parts = [f"{new_price} * {new_units}"]

    for slot in layer.slots:
        if slot.entry is not None and not slot.entry.is_hedge:
            total_cost += slot.entry.entry_price * Decimal(str(slot.entry.units))
            total_units += slot.entry.units
            parts.append(f"{slot.entry.entry_price} * {slot.entry.units}")
        elif slot.pending_rebuild is not None:
            pending = slot.pending_rebuild
            total_cost += pending.entry_price * Decimal(str(pending.units))
            total_units += pending.units
            parts.append(f"{pending.entry_price} * {pending.units}")

    if include_ref is not None:
        ref_units = abs(include_ref.units)
        if ref_units > 0:
            total_cost += include_ref.entry_price * Decimal(str(ref_units))
            total_units += ref_units
            parts.append(f"{include_ref.entry_price} * {ref_units}")

    close_price = total_cost / Decimal(str(total_units)) if total_units > 0 else new_price
    return close_price, f"({' + '.join(parts)}) / {total_units}"


def current_weighted_avg_close_price(layer: Layer) -> tuple[Decimal, str] | None:
    """Compute weighted-average close price from the layer's current state."""
    total_cost = Decimal("0")
    total_units = 0
    parts: list[str] = []

    for slot in layer.slots:
        if slot.entry is not None and not slot.entry.is_hedge:
            total_cost += slot.entry.entry_price * Decimal(str(slot.entry.units))
            total_units += slot.entry.units
            parts.append(f"{slot.entry.entry_price} * {slot.entry.units}")
        elif slot.pending_rebuild is not None:
            pending = slot.pending_rebuild
            total_cost += pending.entry_price * Decimal(str(pending.units))
            total_units += pending.units
            parts.append(f"{pending.entry_price} * {pending.units}")

    if total_units <= 0:
        return None

    close_price = total_cost / Decimal(str(total_units))
    return close_price, f"({' + '.join(parts)}) / {total_units}"


def layer_initial_close_price(
    *,
    new_price: Decimal,
    prev_layer: Layer,
    direction: Direction,
    pip_size: Decimal,
    m_pips: Decimal,
) -> tuple[Decimal, str]:
    """Compute close price for a layer-initial entry from the previous layer."""
    highest = prev_layer.highest_present_slot()
    if highest is not None:
        if highest.entry is not None:
            close_price = highest.entry.close_price
            return close_price, f"{close_price:.5f}"
        if highest.pending_rebuild is not None:
            close_price = highest.pending_rebuild.close_price
            return close_price, f"{close_price:.5f}"

    if direction == Direction.LONG:
        close_price = new_price + m_pips * pip_size
    else:
        close_price = new_price - m_pips * pip_size
    op = "+" if direction == Direction.LONG else "-"
    return close_price, f"{new_price} {op} {m_pips} * {pip_size}"


def sync_weighted_average_counter_take_profits(layer: Layer) -> Decimal | None:
    """Recompute weighted-average TP and apply it to all live counters in a layer."""
    weighted = current_weighted_avg_close_price(layer)
    if weighted is None:
        return None

    close_price = weighted[0]
    for slot in layer.slots:
        if slot.entry is not None and slot.entry.role == "counter":
            slot.entry.close_price = close_price
    return close_price


def sync_entry_fill_price(
    *,
    entry: Entry,
    layer: Layer | None,
    fill_price: Decimal | None,
    counter_tp_mode: str,
) -> None:
    """Align entry pricing with a broker fill price and refresh dependent exits."""
    if fill_price is None:
        return

    fill_price = Decimal(str(fill_price))
    delta = fill_price - entry.entry_price
    if delta == 0:
        return

    entry.entry_price = fill_price

    if entry.stop_loss_price is not None:
        entry.stop_loss_price += delta

    if layer is not None and entry.role == "counter" and counter_tp_mode == "weighted_avg":
        sync_weighted_average_counter_take_profits(layer)
        return

    entry.close_price += delta
