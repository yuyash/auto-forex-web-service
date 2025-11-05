"""
Management command to initialize or update SystemSettings.

This command creates the singleton SystemSettings instance with default values
if it doesn't already exist, or updates existing settings.

Usage:
    python manage.py init_system_settings
    python manage.py init_system_settings --registration-enabled=false
    python manage.py init_system_settings --email-whitelist-enabled=true

Requirements: 1.1, 2.1, 19.5, 28.5
"""

from typing import Any

from django.core.management.base import BaseCommand

from accounts.models import SystemSettings


class Command(BaseCommand):
    """Initialize or update SystemSettings."""

    help = "Initialize or update SystemSettings with specified values"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--registration-enabled",
            type=str,
            choices=["true", "false"],
            help="Enable or disable user registration (true/false)",
        )
        parser.add_argument(
            "--login-enabled",
            type=str,
            choices=["true", "false"],
            help="Enable or disable user login (true/false)",
        )
        parser.add_argument(
            "--email-whitelist-enabled",
            type=str,
            choices=["true", "false"],
            help="Enable or disable email whitelist enforcement (true/false)",
        )
        parser.add_argument(
            "--show",
            action="store_true",
            help="Show current settings without making changes",
        )

    def handle(self, *args: object, **options: object) -> None:
        """
        Execute the command.

        Creates SystemSettings instance if it doesn't exist, or updates existing settings.
        """
        settings = SystemSettings.get_settings()

        # Show current settings if requested
        if options.get("show"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Current SystemSettings:\n"
                    f"  registration_enabled: {settings.registration_enabled}\n"
                    f"  login_enabled: {settings.login_enabled}\n"
                    f"  email_whitelist_enabled: {settings.email_whitelist_enabled}\n"
                    f"  updated_at: {settings.updated_at}"
                )
            )
            return

        # Track if any changes were made
        changes_made = False

        # Update registration_enabled if provided
        if options.get("registration_enabled") is not None:
            new_value = str(options["registration_enabled"]).lower() == "true"
            if settings.registration_enabled != new_value:
                settings.registration_enabled = new_value
                changes_made = True
                self.stdout.write(f"Updated registration_enabled: {new_value}")

        # Update login_enabled if provided
        if options.get("login_enabled") is not None:
            new_value = str(options["login_enabled"]).lower() == "true"
            if settings.login_enabled != new_value:
                settings.login_enabled = new_value
                changes_made = True
                self.stdout.write(f"Updated login_enabled: {new_value}")

        # Update email_whitelist_enabled if provided
        if options.get("email_whitelist_enabled") is not None:
            new_value = str(options["email_whitelist_enabled"]).lower() == "true"
            if settings.email_whitelist_enabled != new_value:
                settings.email_whitelist_enabled = new_value
                changes_made = True
                self.stdout.write(f"Updated email_whitelist_enabled: {new_value}")

        # Save if changes were made
        if changes_made:
            settings.save()
            self.stdout.write(self.style.SUCCESS("\nSystemSettings updated successfully!"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SystemSettings initialized (no changes made):\n"
                    f"  registration_enabled: {settings.registration_enabled}\n"
                    f"  login_enabled: {settings.login_enabled}\n"
                    f"  email_whitelist_enabled: {settings.email_whitelist_enabled}"
                )
            )
