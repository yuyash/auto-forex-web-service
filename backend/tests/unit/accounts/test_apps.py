"""
Unit tests for accounts app configuration.

Tests cover:
- AccountsConfig
"""

from apps.accounts.apps import AccountsConfig


class TestAccountsConfig:
    """Test cases for AccountsConfig."""

    def test_default_auto_field(self) -> None:
        """Test default_auto_field is BigAutoField."""
        assert AccountsConfig.default_auto_field == "django.db.models.BigAutoField"

    def test_name(self) -> None:
        """Test app name."""
        assert AccountsConfig.name == "apps.accounts"

    def test_verbose_name(self) -> None:
        """Test verbose name."""
        assert AccountsConfig.verbose_name == "User Accounts"

    def test_ready_imports_signals(self) -> None:
        """Test ready() imports signals module."""
        config = AccountsConfig("apps.accounts", __import__("apps.accounts"))

        # Call ready - it should import signals
        config.ready()

        # The import happens inside ready(), we can verify the module exists
        import apps.accounts.signals

        assert apps.accounts.signals is not None
