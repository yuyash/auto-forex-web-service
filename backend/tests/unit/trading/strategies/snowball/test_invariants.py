"""Tests for Snowball invariant validation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.invariants import SnowballInvariantValidator
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    PositionGrid,
    SnowballCycle,
    SnowballStrategyState,
)


class SnowballInvariantTestFactory:
    """Build small Snowball state objects for invariant tests."""

    def layer_grid(self, layer: Layer) -> PositionGrid:
        return PositionGrid(layers=[layer])


def test_invariant_validator_accepts_consistent_grid_state():
    factory = SnowballInvariantTestFactory()
    config = SnowballStrategyConfig.from_dict({"r_max": 2, "f_max": 2})
    layer = Layer.create(layer_number=1, r_max=2, base_units=1000)
    slot = layer.slot_at(0)
    assert slot is not None
    slot.entry = Entry(
        entry_id=1,
        step=1,
        direction=Direction.LONG,
        entry_price=Decimal("1.1000"),
        close_price=Decimal("1.1050"),
        units=1000,
        opened_at=datetime(2026, 5, 8, tzinfo=UTC),
        role="initial",
        layer_number=1,
        retracement_count=0,
    )
    state = SnowballStrategyState(
        cycles=[
            SnowballCycle(cycle_id=1, direction=Direction.LONG, grid=factory.layer_grid(layer))
        ],
        next_entry_id=2,
    )

    assert SnowballInvariantValidator(config=config).validate(state).ok


def test_invariant_validator_reports_duplicate_entry_id():
    factory = SnowballInvariantTestFactory()
    config = SnowballStrategyConfig.from_dict({"r_max": 1, "f_max": 2})
    first = Layer.create(layer_number=1, r_max=1, base_units=1000)
    second = Layer.create(layer_number=1, r_max=1, base_units=1000)
    for layer in (first, second):
        slot = layer.slot_at(0)
        assert slot is not None
        slot.entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("1.1000"),
            close_price=Decimal("1.1050"),
            units=1000,
            opened_at=datetime(2026, 5, 8, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
        )
    state = SnowballStrategyState(
        cycles=[
            SnowballCycle(cycle_id=1, direction=Direction.LONG, grid=factory.layer_grid(first)),
            SnowballCycle(cycle_id=2, direction=Direction.LONG, grid=factory.layer_grid(second)),
        ],
        next_entry_id=2,
    )

    report = SnowballInvariantValidator(config=config).validate(state)

    assert not report.ok
    assert "Duplicate entry_id 1" in report.summary()
