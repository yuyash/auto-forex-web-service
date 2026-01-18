"""Unit tests for accounts apps configuration."""

from django.apps import apps

from apps.accounts.apps import AccountsConfig


class TestAccountsConfig:
    """Test AccountsConfig."""

    def test_app_name(self):
        """Test app name is correct."""
        assert AccountsConfig.name == "apps.accounts"

    def test_app_is_registered(self):
        """Test accounts app is registered."""
        app_config = apps.get_app_config("accounts")
        assert app_config.name == "apps.accounts"
        assert isinstance(app_config, AccountsConfig)

    def test_default_auto_field(self):
        """Test default auto field is configured."""
        assert AccountsConfig.default_auto_field == "django.db.models.BigAutoField"
