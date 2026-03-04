"""Management command to delete a strategy configuration."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import StrategyConfiguration


class Command(BaseCommand):
    """Delete a strategy configuration."""

    help = "Delete a strategy configuration by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("config_id", type=str, help="Configuration UUID")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            config_id = UUID(options["config_id"])
        except ValueError:
            raise CommandError(f"Invalid UUID: {options['config_id']}")

        try:
            config = StrategyConfiguration.objects.get(pk=config_id)
        except StrategyConfiguration.DoesNotExist:
            raise CommandError(f"Configuration '{config_id}' not found")

        if config.has_active_tasks():
            raise CommandError(
                f"Configuration '{config.name}' has active tasks. "
                "Stop all tasks using this configuration first."
            )

        if not options["force"]:
            in_use_msg = " (IN USE by tasks)" if config.is_in_use() else ""
            confirm = input(f"Delete configuration '{config.name}'{in_use_msg}? [y/N] ")
            if confirm.lower() != "y":
                self.stdout.write("Cancelled.")
                return

        try:
            config.delete()
        except Exception as e:
            raise CommandError(f"Failed to delete: {e}")

        self.stdout.write(self.style.SUCCESS(f"Deleted configuration: {config_id}"))
