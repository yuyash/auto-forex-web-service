"""Unit tests for trading apps configuration."""

from django.apps import apps

from apps.trading.apps import TradingConfig


class TestTradingConfig:
    """Test TradingConfig."""

    def test_app_name(self):
        """Test app name is correct."""
        assert TradingConfig.name == "apps.trading"

    def test_app_is_registered(self):
        """Test trading app is registered."""
        app_config = apps.get_app_config("trading")
        assert app_config.name == "apps.trading"
        assert isinstance(app_config, TradingConfig)

    def test_default_auto_field(self):
        """Test default auto field is configured."""
        assert TradingConfig.default_auto_field == "django.db.models.BigAutoField"
