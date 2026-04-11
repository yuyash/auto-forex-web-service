"""Unit tests for Snowball strategy models (unified position grid)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import (
    BasketEntry,
    Entry,
    Layer,
    PositionGrid,
    Slot,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _entry(
    entry_id: int = 1,
    direction: Direction = Direction.LONG,
    entry_price: str = "150.00",
    close_price: str = "150.50",
    units: int = 1000,
    role: str = "counter",
    layer_number: int = 1,
    retracement_count: int = 0,
) -> Entry:
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


class TestSnowballStrategyConfig:
    def test_from_dict_defaults(self):
        cfg = SnowballStrategyConfig.from_dict({})
        assert cfg.base_units == 1000
        assert cfg.m_pips == Decimal("50")
        assert cfg.r_max == 7
        assert cfg.f_max == 3
        assert cfg.interval_mode == "constant"
        assert cfg.counter_tp_mode == "weighted_avg"
        assert cfg.disable_loss_cut_after_rebuild is False

    def test_from_dict_custom(self):
        cfg = SnowballStrategyConfig.from_dict(
            {
                "base_units": 2000,
                "m_pips": "30",
                "r_max": 5,
                "interval_mode": "manual",
                "manual_intervals": ["10", "20", "30", "40", "50"],
            }
        )
        assert cfg.base_units == 2000
        assert cfg.m_pips == Decimal("30")
        assert cfg.r_max == 5
        assert len(cfg.manual_intervals) == 5

    def test_to_dict_roundtrip(self):
        cfg = SnowballStrategyConfig.from_dict(
            {"m_pips": "30", "disable_loss_cut_after_rebuild": True}
        )
        d = cfg.to_dict()
        cfg2 = SnowballStrategyConfig.from_dict(d)
        assert cfg2.m_pips == Decimal("30")
        assert cfg2.base_units == cfg.base_units
        assert cfg2.disable_loss_cut_after_rebuild is True

    def test_validate_m_th_n_th_order(self):
        with pytest.raises(ValueError, match="m_th < n_th"):
            SnowballStrategyConfig.from_dict(
                {"shrink_enabled": True, "lock_enabled": True, "m_th": "90", "n_th": "80"}
            ).validate()

    def test_validate_manual_intervals_count(self):
        with pytest.raises(ValueError, match="manual_intervals"):
            SnowballStrategyConfig.from_dict(
                {
                    "interval_mode": "manual",
                    "manual_intervals": ["10", "20"],
                    "r_max": 5,
                    "m_pips": "30",
                }
            ).validate()

    def test_validate_passes_for_valid_config(self):
        cfg = SnowballStrategyConfig.from_dict(
            {
                "shrink_enabled": True,
                "lock_enabled": True,
                "m_th": "70",
                "n_th": "85",
                "m_pips": "30",
            }
        )
        cfg.validate()


class TestBasketEntry:
    def test_to_dict_roundtrip(self):
        entry = BasketEntry(
            entry_id=1,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("150.00"),
            close_price=Decimal("150.50"),
            units=1000,
            opened_at=T0,
            role="initial",
        )
        d = entry.to_dict()
        restored = BasketEntry.from_dict(d)
        assert restored.entry_id == 1
        assert restored.direction == Direction.LONG
        assert restored.units == 1000
        assert restored.entry_price == Decimal("150.00")

    def test_grid_key(self):
        e = _entry(layer_number=2, retracement_count=3)
        assert e.grid_key == (2, 3)


class TestSlot:
    def test_fill_and_close(self):
        slot = Slot(index=1)
        assert slot.is_empty
        assert not slot.ever_closed
        entry = _entry()
        slot.fill(entry)
        assert slot.is_occupied
        closed = slot.close(refillable=False)
        assert closed is entry
        assert slot.is_empty
        assert slot.ever_closed

    def test_refillable_close(self):
        slot = Slot(index=1)
        slot.fill(_entry())
        slot.close(refillable=True)
        assert slot.is_available
        assert not slot.ever_closed

    def test_to_dict_roundtrip(self):
        slot = Slot(index=3, ever_closed=True)
        d = slot.to_dict()
        restored = Slot.from_dict(d)
        assert restored.index == 3
        assert restored.ever_closed is True
        assert restored.entry is None


class TestLayer:
    def test_create_has_r0_through_rmax(self):
        layer = Layer.create(1, 7, 1000)
        assert layer.layer_number == 1
        assert len(layer.slots) == 8  # R0 + R1…R7
        assert layer.slots[0].index == 0
        assert layer.slots[7].index == 7
        assert all(s.is_empty for s in layer.slots)

    def test_next_available_counter_slot_skips_r0(self):
        layer = Layer.create(1, 3, 1000)
        slot = layer.next_available_counter_slot()
        assert slot is not None
        assert slot.index == 1  # R1, not R0

    def test_next_available_counter_slot_after_fill(self):
        layer = Layer.create(1, 3, 1000)
        layer.slots[1].fill(_entry(entry_id=1, retracement_count=1))
        slot = layer.next_available_counter_slot()
        assert slot is not None
        assert slot.index == 2

    def test_needs_new_layer_after_seal(self):
        layer = Layer.create(1, 3, 1000, refill_up_to=0)
        layer.slots[1].fill(_entry(entry_id=1))
        layer.slots[1].close(refillable=False)
        assert layer.needs_new_layer is True

    def test_slot_at(self):
        layer = Layer.create(1, 3, 1000)
        assert layer.slot_at(0) is not None
        assert layer.slot_at(0).index == 0
        assert layer.slot_at(3) is not None
        assert layer.slot_at(4) is None

    def test_close_slot_auto_refillable(self):
        layer = Layer.create(1, 3, 1000, refill_up_to=2)
        layer.slots[1].fill(_entry(entry_id=1))
        layer.close_slot(1)  # R1 <= refill_up_to=2 → refillable
        assert layer.slots[1].is_available

        layer.slots[3].fill(_entry(entry_id=2))
        layer.close_slot(3)  # R3 > refill_up_to=2 → sealed
        assert layer.slots[3].ever_closed

    def test_to_dict_roundtrip(self):
        layer = Layer.create(2, 3, 1500)
        d = layer.to_dict()
        restored = Layer.from_dict(d)
        assert restored.layer_number == 2
        assert len(restored.slots) == 4  # R0…R3
        assert restored.base_units == 1500


class TestPositionGrid:
    def _grid_with_entries(self) -> PositionGrid:
        """L1: R0(id=1), R1(id=2), R2(id=3).  L2: R0(id=4), R1(id=5)."""
        grid = PositionGrid()
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, layer_number=1, retracement_count=0, role="initial"))
        l0.slot_at(1).fill(_entry(entry_id=2, layer_number=1, retracement_count=1))
        l0.slot_at(2).fill(_entry(entry_id=3, layer_number=1, retracement_count=2))
        grid.add_layer(l0)

        l1 = Layer.create(2, 3, 1000)
        l1.slot_at(0).fill(
            _entry(entry_id=4, layer_number=2, retracement_count=0, role="layer_initial")
        )
        l1.slot_at(1).fill(_entry(entry_id=5, layer_number=2, retracement_count=1))
        grid.add_layer(l1)
        return grid

    def test_head_entry_is_oldest(self):
        grid = self._grid_with_entries()
        head = grid.head_entry()
        assert head is not None
        assert head.entry_id == 1

    def test_tail_entry_is_newest(self):
        grid = self._grid_with_entries()
        tail = grid.tail_entry()
        assert tail is not None
        assert tail.entry_id == 5

    def test_head_shifts_after_front_removal(self):
        grid = self._grid_with_entries()
        grid.remove_entry(1)  # remove L0/R0
        head = grid.head_entry()
        assert head is not None
        assert head.entry_id == 2  # L0/R1 is now the oldest

    def test_has_counter_entries(self):
        grid = self._grid_with_entries()
        assert grid.has_counter_entries() is True

    def test_no_counter_entries_when_only_head(self):
        grid = PositionGrid()
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, role="initial"))
        grid.add_layer(l0)
        assert grid.has_counter_entries() is False

    def test_front_entry_with_multi_positions_returns_lowest_r(self):
        """L1 has 3 entries → front_entry returns L1/R0 (lowest R)."""
        grid = self._grid_with_entries()
        front = grid.front_entry()
        assert front is not None
        assert front.entry_id == 1  # L1/R0

    def test_front_entry_skips_single_layer_when_upper_has_multi(self):
        """L1 has 1 entry, L2 has 2 entries → skip L1, return L2/R0."""
        grid = PositionGrid()
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, layer_number=1, retracement_count=0, role="initial"))
        grid.add_layer(l0)

        l1 = Layer.create(2, 3, 1000)
        l1.slot_at(0).fill(
            _entry(entry_id=4, layer_number=2, retracement_count=0, role="layer_initial")
        )
        l1.slot_at(1).fill(_entry(entry_id=5, layer_number=2, retracement_count=1))
        grid.add_layer(l1)

        front = grid.front_entry()
        assert front is not None
        assert front.entry_id == 4  # L2/R0, not L1/R0

    def test_front_entry_closes_single_when_no_upper_multi(self):
        """L1 has 1 entry, L2 has 1 entry → close L1/R0 (no upper multi)."""
        grid = PositionGrid()
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, layer_number=1, retracement_count=0, role="initial"))
        grid.add_layer(l0)

        l1 = Layer.create(2, 3, 1000)
        l1.slot_at(0).fill(
            _entry(entry_id=4, layer_number=2, retracement_count=0, role="layer_initial")
        )
        grid.add_layer(l1)

        front = grid.front_entry()
        assert front is not None
        assert front.entry_id == 1  # L1/R0

    def test_front_entry_progressive_shrink_sequence(self):
        """Simulate a full shrink sequence with the preservation rule.

        Grid: L1:[R0, R1], L2:[R0, R1, R2, R3]
        Expected order:
        1. L1/R0 (L1 has 2 → close lowest R)
        2. L2/R0 (L1 has 1, L2 has 4 → skip L1, close L2 lowest R)
        3. L2/R1 (L1 has 1, L2 has 3 → skip L1, close L2 lowest R)
        4. L2/R2 (L1 has 1, L2 has 2 → skip L1, close L2 lowest R)
        5. L1/R1 (L1 has 1, L2 has 1 → no upper multi, close L1)
        6. L2/R3 (L1 empty, L2 has 1 → close it)
        """
        grid = PositionGrid()
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, layer_number=1, retracement_count=0))
        l0.slot_at(1).fill(_entry(entry_id=2, layer_number=1, retracement_count=1))
        grid.add_layer(l0)

        l1 = Layer.create(2, 3, 1000)
        l1.slot_at(0).fill(_entry(entry_id=10, layer_number=2, retracement_count=0))
        l1.slot_at(1).fill(_entry(entry_id=11, layer_number=2, retracement_count=1))
        l1.slot_at(2).fill(_entry(entry_id=12, layer_number=2, retracement_count=2))
        l1.slot_at(3).fill(_entry(entry_id=13, layer_number=2, retracement_count=3))
        grid.add_layer(l1)

        close_order = []
        for _ in range(6):
            e = grid.front_entry()
            assert e is not None, f"Expected entry but got None after closing {close_order}"
            close_order.append(e.entry_id)
            grid.remove_entry(e.entry_id)

        assert close_order == [1, 10, 11, 12, 2, 13]
        assert grid.front_entry() is None

    def test_is_empty(self):
        grid = PositionGrid()
        grid.add_layer(Layer.create(1, 3, 1000))
        assert grid.is_empty() is True

    def test_all_entries(self):
        grid = self._grid_with_entries()
        assert len(grid.all_entries()) == 5

    def test_is_fully_pending_uses_f_max_as_total_layer_count(self):
        grid = PositionGrid()
        for layer_number in range(1, 4):
            layer = Layer.create(layer_number, 1, 1000)
            layer.slot_at(0).pending_rebuild = object()
            layer.slot_at(1).pending_rebuild = object()
            grid.add_layer(layer)

        assert grid.is_fully_pending(3) is True
        assert grid.is_fully_pending(4) is False


class TestSnowballCycle:
    def test_initial_entry_is_dynamic_head(self):
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        l0 = Layer.create(0, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=10, role="initial"))
        l0.slot_at(1).fill(_entry(entry_id=11))
        cycle.add_layer(l0)

        assert cycle.initial_entry is not None
        assert cycle.initial_entry.entry_id == 10

        # Remove head → initial_entry shifts
        cycle.remove_entry(10)
        assert cycle.initial_entry is not None
        assert cycle.initial_entry.entry_id == 11

    def test_to_dict_roundtrip(self):
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        l0 = Layer.create(0, 3, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, role="initial"))
        l0.slot_at(1).fill(_entry(entry_id=2, retracement_count=1))
        cycle.add_layer(l0)

        d = cycle.to_dict()
        restored = SnowballCycle.from_dict(d)
        assert restored.cycle_id == 1
        assert restored.direction == Direction.LONG
        assert restored.initial_entry is not None
        assert restored.initial_entry.entry_id == 1
        assert len(restored.grid.all_entries()) == 2

    def test_legacy_format_migration(self):
        """Old format with initial_entry + layers should be migrated."""
        legacy = {
            "cycle_id": 1,
            "direction": "long",
            "initial_entry": {
                "entry_id": 1,
                "step": 1,
                "direction": "long",
                "entry_price": "150.00",
                "close_price": "150.50",
                "units": 1000,
                "opened_at": "2026-01-01T00:00:00+00:00",
                "role": "initial",
                "layer_number": 1,
                "retracement_count": 0,
            },
            "layers": [
                {
                    "layer_number": 1,
                    "base_units": 1000,
                    "refill_up_to": 2,
                    "slots": [
                        {
                            "index": 1,
                            "entry": {
                                "entry_id": 2,
                                "direction": "long",
                                "entry_price": "149.70",
                                "close_price": "150.00",
                                "units": 2000,
                                "opened_at": "2026-01-01T00:00:00+00:00",
                                "step": 2,
                                "layer_number": 1,
                                "retracement_count": 1,
                            },
                            "ever_closed": False,
                        },
                    ],
                }
            ],
        }
        cycle = SnowballCycle.from_dict(legacy)
        assert cycle.initial_entry is not None
        assert cycle.initial_entry.entry_id == 1
        assert cycle.initial_entry.layer_number == 0  # migrated from 1 to 0
        entries = cycle.grid.all_entries()
        assert len(entries) == 2


class TestSnowballStrategyState:
    def test_default_state(self):
        ss = SnowballStrategyState()
        assert ss.protection_level == ProtectionLevel.NORMAL
        assert ss.initialised is False
        assert ss.cycles == []

    def test_to_dict_roundtrip(self):
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        l0 = Layer.create(0, 7, 1000)
        l0.slot_at(0).fill(_entry(entry_id=1, role="initial"))
        l0.slot_at(1).fill(_entry(entry_id=2, retracement_count=1))
        cycle.add_layer(l0)

        ss = SnowballStrategyState(
            initialised=True,
            cycles=[cycle],
            protection_level=ProtectionLevel.SHRINK,
        )
        d = ss.to_dict()
        ss2 = SnowballStrategyState.from_dict(d)
        assert ss2.initialised is True
        assert len(ss2.cycles) == 1
        assert ss2.protection_level == ProtectionLevel.SHRINK

    def test_from_strategy_state_none(self):
        ss = SnowballStrategyState.from_strategy_state(None)
        assert ss.initialised is False
