"""
Django app configuration for trading module.
"""

from django.apps import AppConfig


class TradingConfig(AppConfig):
    """Configuration for the trading app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"
    verbose_name = "Trading"
