"""Property-based tests for Snowball grid invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.grid_policy import SNOWBALL_GRID_POLICY
from apps.trading.strategies.snowball.cycle_state import SnowballCycle
from apps.trading.strategies.snowball.entries import Entry, StopLossClosedEntry
from apps.trading.strategies.snowball.grid_models import Layer, Slot


class SnowballGridInvariantHarness:
    """Build and mutate Snowball grids for property tests."""

    base_time = datetime(2026, 5, 8, tzinfo=UTC)

    def monotonic_cycle(
        self,
        *,
        direction: Direction,
        increments: list[int],
        pending_mask: list[bool],
    ) -> SnowballCycle:
        """Create a monotonic cycle with live and pending-rebuild slots."""
        cycle = SnowballCycle(cycle_id=1, direction=direction)
        layer = Layer.create(1, len(increments), 1000, 2)
        running = Decimal("150.000")
        for idx, increment in enumerate(increments):
            offset = Decimal(increment) / Decimal("100")
            running = running - offset if direction == Direction.LONG else running + offset
            close_price = (
                running + Decimal("0.050")
                if direction == Direction.LONG
                else running - Decimal("0.050")
            )
            slot = layer.slot_at(idx)
            assert slot is not None
            if pending_mask[idx]:
                slot.pending_rebuild = self.pending(
                    direction=direction,
                    entry_price=running,
                    close_price=close_price,
                    retracement_count=idx,
                )
            else:
                slot.fill(
                    self.entry(
                        entry_id=idx + 1,
                        direction=direction,
                        entry_price=running,
                        close_price=close_price,
                        retracement_count=idx,
                    )
                )
        cycle.add_layer(layer)
        return cycle

    def out_of_order_cycle(self, *, direction: Direction) -> SnowballCycle:
        """Create a two-slot cycle with an entry-order violation."""
        cycle = SnowballCycle(cycle_id=2, direction=direction)
        layer = Layer.create(1, 2, 1000, 2)
        first_price = Decimal("150.000")
        second_price = Decimal("150.100") if direction == Direction.LONG else Decimal("149.900")
        first = layer.slot_at(0)
        second = layer.slot_at(1)
        assert first is not None and second is not None
        first.fill(
            self.entry(
                entry_id=1,
                direction=direction,
                entry_price=first_price,
                close_price=first_price,
                retracement_count=0,
            )
        )
        second.fill(
            self.entry(
                entry_id=2,
                direction=direction,
                entry_price=second_price,
                close_price=second_price,
                retracement_count=1,
            )
        )
        cycle.add_layer(layer)
        return cycle

    def apply_slot_operations(self, operation_codes: list[int]) -> Layer:
        """Run random slot operations and return the mutated layer."""
        layer = Layer.create(1, 3, 1000, 2)
        next_entry_id = 1
        for operation_code in operation_codes:
            operation = operation_code % 4
            if operation == 0:
                slot = layer.next_available_counter_slot() or layer.slot_at(0)
                if slot is not None and slot.entry is None and slot.pending_rebuild is None:
                    slot.fill(
                        self.entry(
                            entry_id=next_entry_id,
                            direction=Direction.LONG,
                            entry_price=Decimal("150") - Decimal(next_entry_id) / Decimal("100"),
                            close_price=Decimal("150"),
                            retracement_count=slot.index,
                        )
                    )
                    next_entry_id += 1
            elif operation == 1:
                slot = layer.highest_occupied_slot()
                if slot is not None:
                    slot.close(refillable=slot.index > 0)
            elif operation == 2:
                slot = layer.highest_occupied_slot()
                if slot is not None and slot.entry is not None:
                    slot.close_for_stop_loss(
                        self.pending(
                            direction=slot.entry.direction,
                            entry_price=slot.entry.entry_price,
                            close_price=slot.entry.close_price,
                            retracement_count=slot.index,
                        )
                    )
            else:
                slot = self.first_pending_slot(layer)
                if slot is not None and slot.pending_rebuild is not None:
                    pending = slot.pending_rebuild
                    slot.complete_rebuild(
                        self.entry(
                            entry_id=next_entry_id,
                            direction=pending.direction,
                            entry_price=pending.entry_price,
                            close_price=pending.close_price,
                            retracement_count=slot.index,
                        )
                    )
                    next_entry_id += 1
        return layer

    def first_pending_slot(self, layer: Layer) -> Slot | None:
        """Return the first pending-rebuild slot in a layer."""
        for slot in layer.slots:
            if slot.pending_rebuild is not None:
                return slot
        return None

    def entry(
        self,
        *,
        entry_id: int,
        direction: Direction,
        entry_price: Decimal,
        close_price: Decimal,
        retracement_count: int,
    ) -> Entry:
        """Build a grid entry."""
        return Entry(
            entry_id=entry_id,
            step=retracement_count + 1,
            direction=direction,
            entry_price=entry_price,
            close_price=close_price,
            units=1000,
            opened_at=self.base_time,
            role="initial" if retracement_count == 0 else "counter",
            layer_number=1,
            retracement_count=retracement_count,
        )

    def pending(
        self,
        *,
        direction: Direction,
        entry_price: Decimal,
        close_price: Decimal,
        retracement_count: int,
    ) -> StopLossClosedEntry:
        """Build a pending rebuild snapshot."""
        return StopLossClosedEntry(
            entry_price=entry_price,
            close_price=close_price,
            units=1000,
            direction=direction,
            role="initial" if retracement_count == 0 else "counter",
            layer_number=1,
            retracement_count=retracement_count,
            step=retracement_count + 1,
            cycle_id=1,
        )


class TestSnowballGridInvariantsProperty:
    """Exercise grid invariants across generated states and operations."""

    @settings(max_examples=50, deadline=None)
    @given(
        is_long=st.booleans(),
        increments=st.lists(st.integers(min_value=1, max_value=50), min_size=2, max_size=6),
        pending_mask=st.lists(st.booleans(), min_size=2, max_size=6),
    )
    def test_monotonic_live_and_pending_grid_validates(
        self,
        *,
        is_long: bool,
        increments: list[int],
        pending_mask: list[bool],
    ) -> None:
        direction = Direction.LONG if is_long else Direction.SHORT
        aligned_mask = (pending_mask + [False] * len(increments))[: len(increments)]
        cycle = SnowballGridInvariantHarness().monotonic_cycle(
            direction=direction,
            increments=increments,
            pending_mask=aligned_mask,
        )

        assert SNOWBALL_GRID_POLICY.validate_ordering(cycle) is None

    @settings(max_examples=20, deadline=None)
    @given(is_long=st.booleans())
    def test_entry_order_violation_is_detected(self, *, is_long: bool) -> None:
        direction = Direction.LONG if is_long else Direction.SHORT
        cycle = SnowballGridInvariantHarness().out_of_order_cycle(direction=direction)

        assert SNOWBALL_GRID_POLICY.validate_ordering(cycle, check_take_profit=False) is not None

    @settings(max_examples=50, deadline=None)
    @given(
        operation_codes=st.lists(st.integers(min_value=0, max_value=30), min_size=1, max_size=30)
    )
    def test_slot_operations_keep_live_and_pending_states_exclusive(
        self,
        *,
        operation_codes: list[int],
    ) -> None:
        layer = SnowballGridInvariantHarness().apply_slot_operations(operation_codes)

        for slot in layer.slots:
            assert not (slot.entry is not None and slot.pending_rebuild is not None)
            assert slot.is_present == (slot.entry is not None or slot.pending_rebuild is not None)
