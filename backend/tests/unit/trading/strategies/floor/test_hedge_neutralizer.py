"""Unit tests for floor strategy hedge neutralizer."""

from decimal import Decimal

from apps.trading.strategies.floor.hedge_neutralizer import HedgeInstruction, HedgeNeutralizer


class TestHedgeInstruction:
    def test_to_dict(self):
        inst = HedgeInstruction(direction="short", units=1000, layer_index=1, source_entry_id=42)
        d = inst.to_dict()
        assert d["direction"] == "short"
        assert d["units"] == 1000

    def test_frozen(self):
        import pytest

        inst = HedgeInstruction(direction="long", units=500, layer_index=1, source_entry_id=1)
        with pytest.raises(AttributeError):
            inst.units = 999


class TestHedgeNeutralizer:
    def test_compute_hedge_instructions_long(self):
        entries = [{"direction": "long", "units": 1000, "floor_index": 1, "entry_id": 1}]
        result = HedgeNeutralizer.compute_hedge_instructions(entries)
        assert len(result) == 1
        assert result[0].direction == "short"
        assert result[0].units == 1000

    def test_compute_hedge_instructions_short(self):
        entries = [{"direction": "short", "units": 500, "floor_index": 2, "entry_id": 2}]
        result = HedgeNeutralizer.compute_hedge_instructions(entries)
        assert result[0].direction == "long"

    def test_compute_hedge_instructions_zero_units_skipped(self):
        entries = [{"direction": "long", "units": 0, "floor_index": 1, "entry_id": 1}]
        result = HedgeNeutralizer.compute_hedge_instructions(entries)
        assert len(result) == 0

    def test_compute_hedge_instructions_multiple(self):
        entries = [
            {"direction": "long", "units": 1000, "floor_index": 1, "entry_id": 1},
            {"direction": "long", "units": 2000, "floor_index": 1, "entry_id": 2},
        ]
        result = HedgeNeutralizer.compute_hedge_instructions(entries)
        assert len(result) == 2
        assert all(r.direction == "short" for r in result)

    def test_compute_net_exposure_balanced(self):
        entries = [
            {"direction": "long", "units": 1000},
            {"direction": "short", "units": 1000},
        ]
        assert HedgeNeutralizer.compute_net_exposure(entries) == Decimal("0")

    def test_compute_net_exposure_long_bias(self):
        entries = [{"direction": "long", "units": 1000}]
        assert HedgeNeutralizer.compute_net_exposure(entries) == Decimal("1000")
