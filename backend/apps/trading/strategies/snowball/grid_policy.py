"""Grid ordering policy for the Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.cycle_state import SnowballCycle
from apps.trading.strategies.snowball.grid_models import Layer, Slot

__all__ = ["SNOWBALL_GRID_POLICY", "SnowballGridPolicy"]

PresentSlot = tuple[int, int, Decimal, Decimal, str]


@dataclass(frozen=True, slots=True)
class SnowballGridPolicy:
    """Own Snowball grid-ordering and neighboring-bound decisions."""

    def validate_ordering(
        self,
        cycle: SnowballCycle,
        *,
        check_take_profit: bool = True,
    ) -> str | None:
        """Return a violation detail when present slots are not monotonic."""
        present = self._present_slots(cycle)
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
        self,
        cycle: SnowballCycle,
        layer: Layer,
        slot_index: int,
    ) -> Decimal | None:
        """Return the TP bound imposed by preceding occupied or pending slots."""
        hard, soft = self.tp_bounds(cycle, layer, slot_index)
        if hard is None:
            return soft
        if soft is None:
            return hard
        if cycle.direction == Direction.LONG:
            return hard if hard < soft else soft
        return hard if hard > soft else soft

    def tp_bounds(
        self,
        cycle: SnowballCycle,
        layer: Layer,
        slot_index: int,
    ) -> tuple[Decimal | None, Decimal | None]:
        """Return hard and soft TP limits from preceding slots."""
        hard: Decimal | None = None
        soft: Decimal | None = None

        for lyr, slot in self._preceding_slots(cycle, layer, slot_index):
            if slot.entry is not None:
                hard = self._combine_bound(cycle.direction, hard, slot.entry.close_price)
            elif slot.pending_rebuild is not None:
                soft = self._combine_bound(
                    cycle.direction,
                    soft,
                    slot.pending_rebuild.close_price,
                )

        return hard, soft

    def preceding_entry_bound(
        self,
        cycle: SnowballCycle,
        layer: Layer,
        slot_index: int,
    ) -> Decimal | None:
        """Return the tightest entry-price bound from preceding occupied slots."""
        bound: Decimal | None = None

        for _lyr, slot in self._preceding_slots(cycle, layer, slot_index):
            if slot.entry is None:
                continue
            bound = self._combine_bound(cycle.direction, bound, slot.entry.entry_price)

        return bound

    def propagate_pending_rebuild_tp(
        self,
        cycle: SnowballCycle,
        layer: Layer,
        slot_index: int,
        new_tp: Decimal,
    ) -> list[tuple[int, int, Decimal, Decimal]]:
        """Extend preceding pending rebuild TPs to keep grid ordering monotonic."""
        adjusted: list[tuple[int, int, Decimal, Decimal]] = []

        for lyr, slot in self._preceding_slots(cycle, layer, slot_index):
            if slot.pending_rebuild is None:
                continue
            old_tp = slot.pending_rebuild.close_price
            if cycle.direction == Direction.LONG:
                if old_tp < new_tp:
                    slot.pending_rebuild.close_price = new_tp
                    adjusted.append((lyr.layer_number, slot.index, old_tp, new_tp))
            elif old_tp > new_tp:
                slot.pending_rebuild.close_price = new_tp
                adjusted.append((lyr.layer_number, slot.index, old_tp, new_tp))

        return adjusted

    def _present_slots(self, cycle: SnowballCycle) -> list[PresentSlot]:
        present: list[PresentSlot] = []
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
        return present

    def _preceding_slots(
        self,
        cycle: SnowballCycle,
        layer: Layer,
        slot_index: int,
    ) -> list[tuple[Layer, Slot]]:
        preceding: list[tuple[Layer, Slot]] = []
        for lyr in cycle.grid.layers:
            if lyr.layer_number > layer.layer_number:
                continue
            for slot in lyr.slots:
                if lyr is layer and slot.index >= slot_index:
                    continue
                preceding.append((lyr, slot))
        return preceding

    def _combine_bound(
        self,
        direction: Direction,
        existing: Decimal | None,
        candidate: Decimal,
    ) -> Decimal:
        if existing is None:
            return candidate
        if direction == Direction.LONG:
            return candidate if candidate < existing else existing
        return candidate if candidate > existing else existing


SNOWBALL_GRID_POLICY = SnowballGridPolicy()
