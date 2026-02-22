"""Unit tests for apps.py."""

from apps.accounts.apps import AccountsConfig


class TestAccountsConfig:
    """Unit tests for AccountsConfig."""

    def test_app_name(self) -> None:
        """Test app name is correctly set."""
        assert AccountsConfig.name == "apps.accounts"

    def test_default_auto_field(self) -> None:
        """Test default auto field is BigAutoField."""
        assert AccountsConfig.default_auto_field == "django.db.models.BigAutoField"

    def test_ready_method_exists(self) -> None:
        """Test ready method exists and is callable."""
        assert hasattr(AccountsConfig, "ready")
        assert callable(AccountsConfig.ready)
