"""Unit tests for trading engine."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.trading.engine import TradingEngine


class TestTradingEngine:
    """Test TradingEngine class."""

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_init_strategy_via_registry(self, mock_registry, mock_register_all):
        """Engine should create strategy via registry."""
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {"key": "val"}
        mock_instance = MagicMock()
        mock_registry.create.return_value = mock_instance

        engine = TradingEngine(
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
            strategy_config=config,
        )

        assert engine.instrument == "USD_JPY"
        assert engine.strategy is mock_instance
        mock_register_all.assert_called_once_with()
        mock_registry.create.assert_called_once_with(
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
            strategy_config=config,
        )

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_init_unknown_strategy_raises(self, mock_registry, mock_register_all):
        """Engine should raise ValueError for unknown strategy type."""
        config = MagicMock()
        config.strategy_type = "nonexistent"
        mock_registry.create.side_effect = ValueError("Unknown strategy")

        with pytest.raises(ValueError, match="Unknown strategy"):
            TradingEngine(
                instrument="EUR_USD",
                pip_size=Decimal("0.0001"),
                strategy_config=config,
            )

        mock_register_all.assert_called_once_with()

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_on_tick_delegates_to_strategy(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_registry.create.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        tick = MagicMock()
        state = MagicMock()
        state.ticks_processed = 0
        engine.on_tick(tick=tick, state=state)
        mock_strategy.on_tick.assert_called_once_with(tick=tick, state=state)

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_on_start_delegates(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_registry.create.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_start(state=state)
        mock_strategy.on_start.assert_called_once_with(state=state)

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_on_stop_delegates(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_registry.create.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_stop(state=state)
        mock_strategy.on_stop.assert_called_once_with(state=state)

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_on_resume_delegates(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_registry.create.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        state = MagicMock()
        engine.on_resume(state=state)
        mock_strategy.on_resume.assert_called_once_with(state=state)

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_strategy_type_property(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_registry.create.return_value = MagicMock()

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config)
        assert engine.strategy_type.value == "floor"

    @patch("apps.trading.engine.register_all_strategies")
    @patch("apps.trading.engine.registry")
    def test_account_currency_set_on_strategy(self, mock_registry, _mock_register_all):
        config = MagicMock()
        config.strategy_type = "floor"
        config.config_dict = {}
        mock_strategy = MagicMock()
        mock_registry.create.return_value = mock_strategy

        engine = TradingEngine("USD_JPY", Decimal("0.01"), config, account_currency="JPY")
        assert engine.account_currency == "JPY"
        assert mock_strategy.account_currency == "JPY"
