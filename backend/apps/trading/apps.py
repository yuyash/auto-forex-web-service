"""
Django app configuration for trading module.
"""

from django.apps import AppConfig


class TradingConfig(AppConfig):
    """Configuration for the trading app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trading"
    verbose_name = "Trading"

    def ready(self) -> None:
        """
        Initialize the app when Django starts.
        Register all trading strategies and connect signal handlers.
        """
        # Import here to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from apps.trading.strategies.registry import register_all_strategies

        register_all_strategies()

        # Import signals to register handlers
        # pylint: disable=import-outside-toplevel,unused-import
        from apps.trading import signals  # noqa: F401
