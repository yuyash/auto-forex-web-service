"""Grid ordering policy helpers for the Snowball strategy."""

from __future__ import annotations

from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.models import Layer, SnowballCycle


def validate_grid_ordering(cycle: SnowballCycle, *, check_take_profit: bool = True) -> str | None:
    """Return a violation detail when present slots are not monotonic."""
    present: list[tuple[int, int, Decimal, Decimal, str]] = []
    for layer in cycle.grid.layers:
        for slot in layer.slots:
            if slot.entry is not None:
                present.append(
                    (
                        layer.layer_number,
                        slot.index,
                        slot.entry.entry_price,
                        slot.entry.close_price,
                        "open",
                    )
                )
            elif slot.pending_rebuild is not None:
                pending = slot.pending_rebuild
                present.append(
                    (
                        layer.layer_number,
                        slot.index,
                        pending.entry_price,
                        pending.close_price,
                        "pending_rebuild",
                    )
                )

    if len(present) < 2:
        return None

    for prev, curr in zip(present, present[1:], strict=False):
        if cycle.is_long:
            entry_ok = prev[2] >= curr[2]
            tp_ok = prev[3] >= curr[3]
            expected = "descending"
        else:
            entry_ok = prev[2] <= curr[2]
            tp_ok = prev[3] <= curr[3]
            expected = "ascending"

        if entry_ok and (tp_ok or not check_take_profit):
            continue

        return (
            f"cycle_id={cycle.cycle_id}, direction={cycle.direction.value}, "
            f"expected={expected}, "
            f"prev=L{prev[0]}/R{prev[1]}({prev[4]}) "
            f"entry={prev[2]:.5f} tp={prev[3]:.5f}, "
            f"curr=L{curr[0]}/R{curr[1]}({curr[4]}) "
            f"entry={curr[2]:.5f} tp={curr[3]:.5f}, "
            f"entry_ok={entry_ok}, tp_ok={tp_ok}, check_take_profit={check_take_profit}"
        )

    return None


def upper_neighbor_tp_bound(
    cycle: SnowballCycle,
    layer: Layer,
    slot_index: int,
) -> Decimal | None:
    """Return the TP bound imposed by preceding occupied or pending slots."""
    hard, soft = grid_tp_bounds(cycle, layer, slot_index)
    if hard is None:
        return soft
    if soft is None:
        return hard
    if cycle.direction == Direction.LONG:
        return hard if hard < soft else soft
    return hard if hard > soft else soft


def grid_tp_bounds(
    cycle: SnowballCycle,
    layer: Layer,
    slot_index: int,
) -> tuple[Decimal | None, Decimal | None]:
    """Return hard and soft TP limits from preceding slots."""
    direction = cycle.direction
    hard: Decimal | None = None
    soft: Decimal | None = None

    def combine(existing: Decimal | None, candidate: Decimal) -> Decimal:
        if existing is None:
            return candidate
        if direction == Direction.LONG:
            return candidate if candidate < existing else existing
        return candidate if candidate > existing else existing

    for lyr in cycle.grid.layers:
        if lyr.layer_number > layer.layer_number:
            continue
        for slot in lyr.slots:
            if lyr is layer and slot.index >= slot_index:
                continue
            if slot.entry is not None:
                hard = combine(hard, slot.entry.close_price)
            elif slot.pending_rebuild is not None:
                soft = combine(soft, slot.pending_rebuild.close_price)

    return hard, soft


def preceding_entry_bound(
    cycle: SnowballCycle,
    layer: Layer,
    slot_index: int,
) -> Decimal | None:
    """Return the tightest entry-price bound from preceding occupied slots."""
    direction = cycle.direction
    bound: Decimal | None = None

    for lyr in cycle.grid.layers:
        if lyr.layer_number > layer.layer_number:
            continue
        for slot in lyr.slots:
            if lyr is layer and slot.index >= slot_index:
                continue
            if slot.entry is None:
                continue
            entry_price = slot.entry.entry_price
            if bound is None:
                bound = entry_price
            elif direction == Direction.LONG:
                bound = entry_price if entry_price < bound else bound
            else:
                bound = entry_price if entry_price > bound else bound

    return bound


def propagate_pending_rebuild_tp(
    cycle: SnowballCycle,
    layer: Layer,
    slot_index: int,
    new_tp: Decimal,
) -> list[tuple[int, int, Decimal, Decimal]]:
    """Extend preceding pending rebuild TPs to keep grid ordering monotonic."""
    direction = cycle.direction
    adjusted: list[tuple[int, int, Decimal, Decimal]] = []

    for lyr in cycle.grid.layers:
        if lyr.layer_number > layer.layer_number:
            continue
        for slot in lyr.slots:
            if lyr is layer and slot.index >= slot_index:
                continue
            if slot.pending_rebuild is None:
                continue
            old_tp = slot.pending_rebuild.close_price
            if direction == Direction.LONG:
                if old_tp < new_tp:
                    slot.pending_rebuild.close_price = new_tp
                    adjusted.append((lyr.layer_number, slot.index, old_tp, new_tp))
            elif old_tp > new_tp:
                slot.pending_rebuild.close_price = new_tp
                adjusted.append((lyr.layer_number, slot.index, old_tp, new_tp))

    return adjusted
