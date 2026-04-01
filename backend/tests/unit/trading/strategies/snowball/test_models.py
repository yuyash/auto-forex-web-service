"""Unit tests for Snowball strategy models."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import (
    BasketEntry,
    Entry,
    Layer,
    Slot,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
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
        assert cfg.interval_mode == "manual"
        assert len(cfg.manual_intervals) == 5

    def test_to_dict_roundtrip(self):
        cfg = SnowballStrategyConfig.from_dict({"m_pips": "30"})
        d = cfg.to_dict()
        cfg2 = SnowballStrategyConfig.from_dict(d)
        assert cfg2.m_pips == Decimal("30")
        assert cfg2.base_units == cfg.base_units

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
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
        )
        d = entry.to_dict()
        restored = BasketEntry.from_dict(d)
        assert restored.entry_id == 1
        assert restored.direction == Direction.LONG
        assert restored.units == 1000
        assert restored.entry_price == Decimal("150.00")


class TestSlot:
    def test_fill_and_vacate(self):
        slot = Slot(index=1)
        assert slot.is_empty
        assert not slot.ever_closed
        entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("100"),
            close_price=Decimal("101"),
            units=1000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
        )
        slot.fill(entry)
        assert slot.is_occupied
        closed = slot.close(refillable=False)
        assert closed is entry
        assert slot.is_empty
        assert slot.ever_closed

    def test_to_dict_roundtrip(self):
        slot = Slot(index=3, ever_closed=True)
        d = slot.to_dict()
        restored = Slot.from_dict(d)
        assert restored.index == 3
        assert restored.ever_closed is True
        assert restored.entry is None


class TestLayer:
    def test_create(self):
        layer = Layer.create(1, 7, 1000)
        assert layer.layer_number == 1
        assert len(layer.slots) == 7
        assert all(s.is_empty for s in layer.slots)

    def test_next_slot_to_fill(self):
        layer = Layer.create(1, 3, 1000)
        assert layer.next_available_slot().index == 1
        layer.slots[0].fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("100"),
                close_price=Decimal("101"),
                units=1000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="counter",
            )
        )
        assert layer.next_available_slot().index == 2

    def test_should_start_new_layer_after_vacate(self):
        layer = Layer.create(1, 3, 1000, refill_up_to=0)
        entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("100"),
            close_price=Decimal("101"),
            units=1000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
        )
        layer.slots[0].fill(entry)
        layer.slots[0].close(refillable=False)
        assert layer.needs_new_layer is True

    def test_to_dict_roundtrip(self):
        layer = Layer.create(2, 3, 1500)
        d = layer.to_dict()
        restored = Layer.from_dict(d)
        assert restored.layer_number == 2
        assert len(restored.slots) == 3
        assert restored.base_units == 1500


class TestSnowballStrategyState:
    def test_default_state(self):
        ss = SnowballStrategyState()
        assert ss.protection_level == ProtectionLevel.NORMAL
        assert ss.initialised is False
        assert ss.cycles == []

    def test_to_dict_roundtrip(self):
        initial = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("150.00"),
            close_price=Decimal("150.50"),
            units=1000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
        )
        layer = Layer.create(1, 7, 1000)
        layer.slots[0].fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.LONG,
                entry_price=Decimal("149.70"),
                close_price=Decimal("150.00"),
                units=2000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="counter",
                layer_number=1,
                retracement_count=1,
            )
        )
        cycle = SnowballCycle(
            cycle_id=1,
            direction=Direction.LONG,
            initial_entry=initial,
            layers=[layer],
        )
        ss = SnowballStrategyState(
            initialised=True,
            cycles=[cycle],
            protection_level=ProtectionLevel.SHRINK,
        )
        d = ss.to_dict()
        ss2 = SnowballStrategyState.from_dict(d)
        assert ss2.initialised is True
        assert len(ss2.cycles) == 1
        assert ss2.cycles[0].layer_retracement_count == 1
        assert ss2.cycles[0].layer_index == 0
        assert ss2.protection_level == ProtectionLevel.SHRINK

    def test_from_strategy_state_none(self):
        ss = SnowballStrategyState.from_strategy_state(None)
        assert ss.initialised is False

    def test_from_strategy_state_dict(self):
        ss = SnowballStrategyState.from_strategy_state(
            {
                "initialised": True,
                "cycles": [
                    {
                        "cycle_id": 1,
                        "direction": "long",
                        "initial_entry": {"entry_id": 1},
                        "layers": [
                            {
                                "layer_number": 1,
                                "base_units": 1000,
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
                                        },
                                        "ever_closed": False,
                                    },
                                    {
                                        "index": 2,
                                        "entry": {
                                            "entry_id": 3,
                                            "direction": "long",
                                            "entry_price": "149.40",
                                            "close_price": "150.00",
                                            "units": 3000,
                                            "opened_at": "2026-01-01T00:00:00+00:00",
                                            "step": 3,
                                        },
                                        "ever_closed": False,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        )
        assert ss.initialised is True
        assert ss.cycles[0].layer_retracement_count == 2
