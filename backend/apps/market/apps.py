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
        # Register signals
        from . import signals as _signals  # noqa: F401

        _ = _signals
