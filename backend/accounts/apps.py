"""
Accounts app configuration.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "User Accounts"

    def ready(self) -> None:
        """
        Import signal handlers when the app is ready.

        This ensures that signal handlers are registered when Django starts.
        """
        # pylint: disable=import-outside-toplevel,unused-import
        import accounts.signals  # noqa: F401
