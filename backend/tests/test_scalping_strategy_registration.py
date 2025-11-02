"""
Unit tests for Scalping Strategy registration.

Tests that the Scalping Strategy is properly registered in the strategy registry.

Requirements: 5.1
"""

from trading.scalping_strategy import ScalpingStrategy
from trading.strategy_registry import registry


class TestScalpingStrategyRegistration:
    """Test Scalping Strategy registration."""

    def test_scalping_strategy_is_registered(self):
        """Test that Scalping Strategy is registered in the registry."""
        assert registry.is_registered("scalping")

    def test_scalping_strategy_class_retrieval(self):
        """Test retrieving Scalping Strategy class from registry."""
        strategy_class = registry.get_strategy_class("scalping")
        assert strategy_class == ScalpingStrategy

    def test_scalping_strategy_in_list(self):
        """Test that Scalping Strategy appears in list of strategies."""
        strategies = registry.list_strategies()
        assert "scalping" in strategies

    def test_scalping_strategy_config_schema(self):
        """Test that Scalping Strategy has a configuration schema."""
        schema = registry.get_config_schema("scalping")

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "base_units" in schema["properties"]
        assert "momentum_lookback_seconds" in schema["properties"]
        assert "min_momentum_pips" in schema["properties"]
        assert "stop_loss_pips" in schema["properties"]
        assert "take_profit_pips" in schema["properties"]
        assert "max_holding_minutes" in schema["properties"]

    def test_scalping_strategy_info(self):
        """Test retrieving Scalping Strategy info."""
        all_info = registry.get_all_strategies_info()

        assert "scalping" in all_info
        assert all_info["scalping"]["name"] == "scalping"
        assert all_info["scalping"]["class_name"] == "ScalpingStrategy"
        assert "config_schema" in all_info["scalping"]
