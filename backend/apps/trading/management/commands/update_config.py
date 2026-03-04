"""Management command to update a strategy configuration."""

import json
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import StrategyConfiguration


class Command(BaseCommand):
    """Update a strategy configuration."""

    help = "Update a strategy configuration by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("config_id", type=str, help="Configuration UUID")
        parser.add_argument("--name", type=str, default=None, help="New name")
        parser.add_argument("--strategy-type", type=str, default=None, help="New strategy type")
        parser.add_argument(
            "--parameters", type=str, default=None, help="New parameters as JSON string"
        )
        parser.add_argument("--description", type=str, default=None, help="New description")

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

        update_fields: list[str] = []

        if options["name"] is not None:
            config.name = options["name"]
            update_fields.append("name")

        if options["strategy_type"] is not None:
            config.strategy_type = options["strategy_type"]
            update_fields.append("strategy_type")

        if options["parameters"] is not None:
            try:
                config.parameters = json.loads(options["parameters"])
                update_fields.append("parameters")
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON for parameters: {e}")

        if options["description"] is not None:
            config.description = options["description"]
            update_fields.append("description")

        if not update_fields:
            self.stdout.write("No fields to update.")
            return

        update_fields.append("updated_at")
        try:
            config.save(update_fields=update_fields)
        except Exception as e:
            raise CommandError(f"Failed to update: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated configuration: {config.pk} '{config.name}' "
                f"(fields: {', '.join(update_fields)})"
            )
        )
