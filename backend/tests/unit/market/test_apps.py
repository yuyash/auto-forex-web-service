"""Unit tests for market apps configuration."""

from django.apps import apps

from apps.market.apps import MarketConfig


class TestMarketConfig:
    """Test MarketConfig."""

    def test_app_name(self):
        """Test app name is correct."""
        assert MarketConfig.name == "apps.market"

    def test_app_is_registered(self):
        """Test market app is registered."""
        app_config = apps.get_app_config("market")
        assert app_config.name == "apps.market"
        assert isinstance(app_config, MarketConfig)

    def test_default_auto_field(self):
        """Test default auto field is configured."""
        assert MarketConfig.default_auto_field == "django.db.models.BigAutoField"
