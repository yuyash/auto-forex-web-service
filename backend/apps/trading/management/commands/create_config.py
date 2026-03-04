"""Management command to create a strategy configuration."""

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.trading.models import StrategyConfiguration


class Command(BaseCommand):
    """Create a new strategy configuration."""

    help = "Create a new strategy configuration"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("--name", type=str, required=True, help="Configuration name")
        parser.add_argument("--email", type=str, required=True, help="User email")
        parser.add_argument(
            "--strategy-type", type=str, required=True, help="Strategy type (e.g. floor, custom)"
        )
        parser.add_argument(
            "--parameters",
            type=str,
            default="{}",
            help='Strategy parameters as JSON string (e.g. \'{"key": "value"}\')',
        )
        parser.add_argument("--description", type=str, default="", help="Description")

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            user = User.objects.get(email=options["email"])
        except User.DoesNotExist:
            raise CommandError(f"User with email '{options['email']}' not found")

        try:
            parameters = json.loads(options["parameters"])
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON for parameters: {e}")

        try:
            config = StrategyConfiguration.objects.create(
                user=user,
                name=options["name"],
                strategy_type=options["strategy_type"],
                parameters=parameters,
                description=options["description"],
            )
        except Exception as e:
            raise CommandError(f"Failed to create configuration: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Created strategy configuration: {config.pk} '{config.name}' "
                f"(type={config.strategy_type})"
            )
        )
