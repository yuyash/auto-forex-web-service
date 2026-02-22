"""Unit tests for trading apps.py."""

from unittest.mock import patch

from apps.trading.apps import TradingConfig


class TestTradingConfig:
    """Test TradingConfig app configuration."""

    def test_name(self):
        assert TradingConfig.name == "apps.trading"

    def test_verbose_name(self):
        assert TradingConfig.verbose_name == "Trading"

    def test_default_auto_field(self):
        assert TradingConfig.default_auto_field == "django.db.models.BigAutoField"

    @patch("apps.trading.strategies.registry.register_all_strategies")
    def test_ready_registers_strategies(self, mock_register):
        """Test that ready() calls register_all_strategies."""
        config = TradingConfig("apps.trading", __import__("apps.trading"))
        with patch.dict("sys.modules", {"apps.trading.signals": None}):
            config.ready()
        mock_register.assert_called_once()
