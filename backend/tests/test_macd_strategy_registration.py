"""
Test MACD Strategy registration with the strategy registry.

Requirements: 5.1, 5.3
"""

from trading.macd_strategy import MACDStrategy
from trading.strategy_registry import registry


class TestMACDStrategyRegistration:
    """Test MACD Strategy registration."""

    def test_macd_strategy_is_registered(self):
        """Test that MACD Strategy is registered in the registry."""
        assert registry.is_registered("macd")

    def test_macd_strategy_class_retrieval(self):
        """Test retrieving MACD Strategy class from registry."""
        strategy_class = registry.get_strategy_class("macd")
        assert strategy_class == MACDStrategy

    def test_macd_strategy_in_list(self):
        """Test that MACD Strategy appears in list of strategies."""
        strategies = registry.list_strategies()
        assert "macd" in strategies

    def test_macd_strategy_config_schema(self):
        """Test that MACD Strategy has a configuration schema."""
        schema = registry.get_config_schema("macd")

        assert schema is not None
        assert "properties" in schema
        assert "fast_period" in schema["properties"]
        assert "slow_period" in schema["properties"]
        assert "signal_period" in schema["properties"]
        assert "base_units" in schema["properties"]
        assert "use_histogram_confirmation" in schema["properties"]

    def test_macd_strategy_info(self):
        """Test retrieving MACD Strategy info."""
        all_info = registry.get_all_strategies_info()

        assert "macd" in all_info
        macd_info = all_info["macd"]

        assert macd_info["name"] == "macd"
        assert macd_info["class_name"] == "MACDStrategy"
        assert "config_schema" in macd_info
        assert macd_info["description"] is not None
