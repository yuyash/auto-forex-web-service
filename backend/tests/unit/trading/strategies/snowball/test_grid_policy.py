"""Unit tests for Snowball grid policy helpers."""

from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.grid_policy import SNOWBALL_GRID_POLICY
from apps.trading.strategies.snowball.cycle_state import SnowballCycle
from apps.trading.strategies.snowball.grid_models import Layer

from .test_models import _entry


def _cycle_with_layer(direction: Direction = Direction.LONG) -> tuple[SnowballCycle, Layer]:
    cycle = SnowballCycle(cycle_id=1, direction=direction)
    layer = Layer.create(1, r_max=2, base_units=1000, refill_up_to=0)
    cycle.add_layer(layer)
    return cycle, layer


def test_validate_grid_ordering_returns_none_for_monotonic_long_grid():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="149.50", close_price="150.00", retracement_count=1)
    )

    assert SNOWBALL_GRID_POLICY.validate_ordering(cycle) is None


def test_validate_grid_ordering_reports_violation_detail():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="150.10", close_price="150.60", retracement_count=1)
    )

    detail = SNOWBALL_GRID_POLICY.validate_ordering(cycle)

    assert detail is not None
    assert "expected=descending" in detail
    assert "entry_ok=False" in detail


def test_validate_grid_ordering_can_ignore_take_profit_ordering():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="149.50", close_price="150.60", retracement_count=1)
    )

    assert SNOWBALL_GRID_POLICY.validate_ordering(cycle) is not None
    assert SNOWBALL_GRID_POLICY.validate_ordering(cycle, check_take_profit=False) is None


def test_validate_grid_ordering_still_reports_entry_violation_when_tp_ignored():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="150.10", close_price="150.40", retracement_count=1)
    )

    detail = SNOWBALL_GRID_POLICY.validate_ordering(cycle, check_take_profit=False)

    assert detail is not None
    assert "entry_ok=False" in detail
    assert "check_take_profit=False" in detail


def test_tp_and_entry_bounds_use_preceding_slots_only():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="149.50", close_price="150.00", retracement_count=1)
    )

    assert SNOWBALL_GRID_POLICY.tp_bounds(cycle, layer, 2) == (Decimal("150.00"), None)
    assert SNOWBALL_GRID_POLICY.upper_neighbor_tp_bound(cycle, layer, 2) == Decimal("150.00")
    assert SNOWBALL_GRID_POLICY.preceding_entry_bound(cycle, layer, 2) == Decimal("149.50")


def test_propagate_pending_rebuild_tp_adjusts_prior_pending_slots():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    pending = _entry(entry_id=1, entry_price="150.00", close_price="150.10")
    layer.slot_at(0).pending_rebuild = pending

    adjusted = SNOWBALL_GRID_POLICY.propagate_pending_rebuild_tp(cycle, layer, 1, Decimal("150.40"))

    assert adjusted == [(1, 0, Decimal("150.10"), Decimal("150.40"))]
    assert pending.close_price == Decimal("150.40")
