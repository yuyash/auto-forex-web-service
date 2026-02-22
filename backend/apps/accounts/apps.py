"""
Accounts app configuration.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "User Accounts"

    def ready(self) -> None:
        """
        Import signal handlers and schema extensions when the app is ready.

        This ensures that signal handlers and OpenAPI extensions are registered
        when Django starts.
        """
        # pylint: disable=import-outside-toplevel,unused-import
        import apps.accounts.schema  # noqa: F401
        import apps.accounts.signals  # noqa: F401
