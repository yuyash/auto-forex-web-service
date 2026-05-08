"""Production-derived Snowball scenario regression tests."""

from __future__ import annotations

import logging
from decimal import Decimal

from apps.trading.strategies.snowball.models import SnowballStrategyState
from tests.unit.trading.strategies.snowball.production_scenarios import (
    SnowballProductionScenarioFactory,
)


class TestSnowballProductionScenarios:
    """Exercise production-derived Snowball failure and recovery shapes."""

    def test_short_rebuild_ghost_guard_does_not_stop_task(self):
        scenario = SnowballProductionScenarioFactory().short_rebuild_ghost_guard()

        result = scenario.strategy.on_tick(tick=scenario.tick, state=scenario.state)

        assert result.should_stop is False
        assert result.is_error is False

    def test_validation_disabled_grid_violation_continues_without_public_error(self, caplog):
        scenario = SnowballProductionScenarioFactory().ignored_grid_violation()

        with caplog.at_level(
            logging.WARNING,
            logger="apps.trading.strategies.snowball.strategy",
        ):
            result = scenario.strategy.on_tick(tick=scenario.tick, state=scenario.state)

        assert result.should_stop is False
        assert result.is_error is False
        assert result.stop_reason == ""
        assert any(
            "Grid ordering violation ignored" in record.getMessage() for record in caplog.records
        )

    def test_cross_layer_pending_rebuild_recovers_grid_ordering(self):
        scenario = SnowballProductionScenarioFactory().cross_layer_pending_rebuild()

        scenario.strategy._process_stop_loss_rebuilds(
            scenario.snowball_state,
            scenario.tick,
            scenario.cycle,
        )

        l1 = scenario.cycle.layers[0]
        l2 = scenario.cycle.layers[1]
        expected_l2r0_tp = Decimal("130.64392")
        assert l2.slots[0].entry is not None
        assert l2.slots[0].entry.close_price == expected_l2r0_tp
        assert l1.slots[7].pending_rebuild is not None
        assert l1.slots[7].pending_rebuild.close_price == expected_l2r0_tp

        scenario.strategy._grid_order_violation = None
        scenario.strategy._validate_grid_ordering(scenario.cycle)
        persisted = SnowballStrategyState.from_strategy_state(scenario.snowball_state.to_dict())
        assert scenario.strategy._grid_order_violation is None
        assert persisted.initialised is True
