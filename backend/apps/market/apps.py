"""
Django app configuration for market app.
"""

from django.apps import AppConfig


class MarketConfig(AppConfig):
    """Configuration for the market app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.market"
    label = "market"
    verbose_name = "Market Data"

    def ready(self) -> None:
        """Initialize app when Django starts."""
        # Import and connect signal handlers
        from apps.market.signals import connect_all_handlers

        connect_all_handlers()
