"""Unit tests for trading strategies registry."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from apps.trading.strategies.registry import StrategyInfo, StrategyRegistry


class TestStrategyRegistry:
    """Test StrategyRegistry class."""

    def test_register_and_is_registered(self):
        reg = StrategyRegistry()
        cls = MagicMock()
        reg.register(identifier="test", strategy_cls=cls)
        assert reg.is_registered("test") is True
        assert reg.is_registered("unknown") is False

    def test_register_empty_identifier_raises(self):
        reg = StrategyRegistry()
        with pytest.raises(ValueError, match="non-empty"):
            reg.register(identifier="", strategy_cls=MagicMock())

    def test_register_duplicate_raises(self):
        reg = StrategyRegistry()
        cls = MagicMock()
        reg.register(identifier="dup", strategy_cls=cls)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(identifier="dup", strategy_cls=MagicMock())

    def test_list_strategies(self):
        reg = StrategyRegistry()
        reg.register(identifier="b", strategy_cls=MagicMock())
        reg.register(identifier="a", strategy_cls=MagicMock())
        assert reg.list_strategies() == ["a", "b"]

    def test_get_all_strategies_info(self):
        reg = StrategyRegistry()
        reg.register(
            identifier="test",
            strategy_cls=MagicMock(),
            config_schema={"prop": "val"},
            display_name="Test Strategy",
            description="A test",
        )
        info = reg.get_all_strategies_info()
        assert "test" in info
        assert info["test"]["display_name"] == "Test Strategy"
        assert info["test"]["description"] == "A test"

    def test_create_unknown_strategy_raises(self):
        reg = StrategyRegistry()
        config = MagicMock()
        config.strategy_type = "nonexistent"
        with pytest.raises(ValueError, match="Unknown strategy"):
            reg.create(
                instrument="EUR_USD",
                pip_size=Decimal("0.0001"),
                strategy_config=config,
            )

    def test_create_calls_parse_config_and_init(self):
        reg = StrategyRegistry()
        mock_cls = MagicMock()
        mock_parsed = MagicMock()
        mock_cls.parse_config.return_value = mock_parsed
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        reg.register(identifier="mock", strategy_cls=mock_cls)
        config = MagicMock()
        config.strategy_type = "mock"

        result = reg.create(
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
            strategy_config=config,
        )
        mock_cls.parse_config.assert_called_once_with(config)
        mock_cls.assert_called_once_with("USD_JPY", Decimal("0.01"), mock_parsed)
        assert result is mock_instance


class TestStrategyInfo:
    """Test StrategyInfo dataclass."""

    def test_frozen(self):
        info = StrategyInfo(
            identifier="test",
            strategy_cls=MagicMock,
            config_schema={},
            display_name="Test",
            description="desc",
        )
        with pytest.raises(AttributeError):
            info.identifier = "changed"
