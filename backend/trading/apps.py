"""
Django app configuration for trading module.
"""

from django.apps import AppConfig


class TradingConfig(AppConfig):
    """Configuration for the trading app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"
    verbose_name = "Trading"

    def ready(self) -> None:
        """
        Initialize the app when Django starts.
        Register all trading strategies.
        """
        # Import here to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from .register_strategies import register_all_strategies

        register_all_strategies()
