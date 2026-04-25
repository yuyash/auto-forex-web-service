"""Unit tests for Snowball grid policy helpers."""

from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.grid_policy import (
    grid_tp_bounds,
    preceding_entry_bound,
    propagate_pending_rebuild_tp,
    upper_neighbor_tp_bound,
    validate_grid_ordering,
)
from apps.trading.strategies.snowball.models import Layer, SnowballCycle

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

    assert validate_grid_ordering(cycle) is None


def test_validate_grid_ordering_reports_violation_detail():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="150.10", close_price="150.60", retracement_count=1)
    )

    detail = validate_grid_ordering(cycle)

    assert detail is not None
    assert "expected=descending" in detail
    assert "entry_ok=False" in detail


def test_tp_and_entry_bounds_use_preceding_slots_only():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    layer.slot_at(0).fill(_entry(entry_id=1, entry_price="150.00", close_price="150.50"))
    layer.slot_at(1).fill(
        _entry(entry_id=2, entry_price="149.50", close_price="150.00", retracement_count=1)
    )

    assert grid_tp_bounds(cycle, layer, 2) == (Decimal("150.00"), None)
    assert upper_neighbor_tp_bound(cycle, layer, 2) == Decimal("150.00")
    assert preceding_entry_bound(cycle, layer, 2) == Decimal("149.50")


def test_propagate_pending_rebuild_tp_adjusts_prior_pending_slots():
    cycle, layer = _cycle_with_layer(Direction.LONG)
    pending = _entry(entry_id=1, entry_price="150.00", close_price="150.10")
    layer.slot_at(0).pending_rebuild = pending

    adjusted = propagate_pending_rebuild_tp(cycle, layer, 1, Decimal("150.40"))

    assert adjusted == [(1, 0, Decimal("150.10"), Decimal("150.40"))]
    assert pending.close_price == Decimal("150.40")
