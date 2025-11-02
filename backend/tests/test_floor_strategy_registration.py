"""
Test Floor Strategy registration with the strategy registry.

Requirements: 13.1
"""

from trading.floor_strategy import FloorStrategy
from trading.strategy_registry import registry


class TestFloorStrategyRegistration:
    """Test Floor Strategy registration."""

    def test_floor_strategy_is_registered(self):
        """Test that Floor Strategy is registered in the registry."""
        assert registry.is_registered("floor")

    def test_floor_strategy_class_retrieval(self):
        """Test retrieving Floor Strategy class from registry."""
        strategy_class = registry.get_strategy_class("floor")
        assert strategy_class == FloorStrategy

    def test_floor_strategy_in_list(self):
        """Test that Floor Strategy appears in list of strategies."""
        strategies = registry.list_strategies()
        assert "floor" in strategies

    def test_floor_strategy_config_schema(self):
        """Test that Floor Strategy has a configuration schema."""
        schema = registry.get_config_schema("floor")

        assert schema is not None
        assert "properties" in schema
        assert "base_lot_size" in schema["properties"]
        assert "scaling_mode" in schema["properties"]
        assert "retracement_pips" in schema["properties"]
        assert "take_profit_pips" in schema["properties"]

    def test_floor_strategy_info(self):
        """Test retrieving Floor Strategy info."""
        all_info = registry.get_all_strategies_info()

        assert "floor" in all_info
        floor_info = all_info["floor"]

        assert floor_info["name"] == "floor"
        assert floor_info["class_name"] == "FloorStrategy"
        assert "config_schema" in floor_info
        assert floor_info["description"] is not None
