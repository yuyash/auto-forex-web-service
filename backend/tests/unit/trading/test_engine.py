"""Unit tests for trading engine."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.trading.engine import TradingEngine
from apps.trading.enums import StrategyType


class TestTradingEngine:
    """Test TradingEngine class."""

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_init_floor_strategy(self, mock_config_cls, mock_strategy_cls):
        """Engine should create FloorStrategy for floor type."""
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {"key": "val"}
        mock_parsed = MagicMock()
        mock_config_cls.from_dict.return_value = mock_parsed
        mock_instance = MagicMock()
        mock_strategy_cls.return_value = mock_instance

        engine = TradingEngine(
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
            strategy_config=config,
        )
        assert engine.instrument == "USD_JPY"
        assert engine.strategy is mock_instance

    def test_init_unknown_strategy_raises(self):
        """Engine should raise ValueError for unknown strategy type."""
        config = MagicMock()
        config.strategy_type = "nonexistent"
        with pytest.raises(ValueError, match="Unknown strategy"):
            TradingEngine(
                instrument="EUR_USD",
                pip_size=Decimal("0.0001"),
                strategy_config=config,
            )

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_on_tick_delegates_to_strategy(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_strategy_cls.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        tick = MagicMock()
        state = MagicMock()
        state.ticks_processed = 0
        engine.on_tick(tick=tick, state=state)
        mock_strategy.on_tick.assert_called_once_with(tick=tick, state=state)

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_on_start_delegates(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_strategy_cls.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_start(state=state)
        mock_strategy.on_start.assert_called_once_with(state=state)

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_on_stop_delegates(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_strategy_cls.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_stop(state=state)
        mock_strategy.on_stop.assert_called_once_with(state=state)

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_on_resume_delegates(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_strategy_cls.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_resume(state=state)
        mock_strategy.on_resume.assert_called_once_with(state=state)

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_strategy_type_property(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        assert engine.strategy_type == StrategyType.FLOOR

    @patch("apps.trading.strategies.floor.strategy.FloorStrategy")
    @patch("apps.trading.strategies.floor.models.FloorStrategyConfig")
    def test_account_currency_set_on_strategy(self, mock_config_cls, mock_strategy_cls):
        config = MagicMock()
        config.strategy_type = StrategyType.FLOOR.value
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_strategy_cls.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config, account_currency="JPY")
        assert engine.account_currency == "JPY"
        assert mock_strategy.account_currency == "JPY"
