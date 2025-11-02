"""
Management command to initialize SystemSettings.

This command creates the singleton SystemSettings instance with default values
if it doesn't already exist.

Usage:
    python manage.py init_system_settings

Requirements: 1.1, 2.1, 19.5, 28.5
"""

from django.core.management.base import BaseCommand

from accounts.models import SystemSettings


class Command(BaseCommand):
    """Initialize SystemSettings with default values."""

    help = "Initialize SystemSettings with default values"

    def handle(self, *args: object, **options: object) -> None:
        """
        Execute the command.

        Creates SystemSettings instance if it doesn't exist.
        """
        settings = SystemSettings.get_settings()

        self.stdout.write(
            self.style.SUCCESS(
                f"SystemSettings initialized: "
                f"registration_enabled={settings.registration_enabled}, "
                f"login_enabled={settings.login_enabled}"
            )
        )
