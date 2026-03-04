"""Management command to update a trading task."""

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration, TradingTask


class Command(BaseCommand):
    """Update a trading task."""

    help = "Update a trading task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Trading task UUID")
        parser.add_argument("--name", type=str, default=None, help="New task name")
        parser.add_argument("--description", type=str, default=None)
        parser.add_argument("--config-name", type=str, default=None)
        parser.add_argument("--account-id", type=str, default=None, help="New OANDA account ID")
        parser.add_argument("--instrument", type=str, default=None)
        parser.add_argument("--pip-size", type=str, default=None)
        parser.add_argument(
            "--sell-on-stop",
            type=str,
            default=None,
            choices=["true", "false"],
            help="Close positions on stop (true/false)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            task_id = UUID(options["task_id"])
        except ValueError:
            raise CommandError(f"Invalid UUID: {options['task_id']}")

        try:
            task = TradingTask.objects.get(pk=task_id)
        except TradingTask.DoesNotExist:
            raise CommandError(f"Trading task '{task_id}' not found")

        update_fields: list[str] = []

        if options["name"] is not None:
            task.name = options["name"]
            update_fields.append("name")

        if options["description"] is not None:
            task.description = options["description"]
            update_fields.append("description")

        if options["config_name"] is not None:
            try:
                config = StrategyConfiguration.objects.get(
                    user=task.user, name=options["config_name"]
                )
                task.config = config
                update_fields.append("config")
            except StrategyConfiguration.DoesNotExist:
                raise CommandError(f"Config '{options['config_name']}' not found for user")

        if options["account_id"] is not None:
            try:
                account = OandaAccounts.objects.get(
                    user=task.user, account_id=options["account_id"]
                )
                task.oanda_account = account
                update_fields.append("oanda_account")
            except OandaAccounts.DoesNotExist:
                raise CommandError(f"OANDA account '{options['account_id']}' not found for user")

        if options["instrument"] is not None:
            task.instrument = options["instrument"]
            update_fields.append("instrument")

        if options["pip_size"] is not None:
            try:
                task.pip_size = Decimal(options["pip_size"])
                update_fields.append("pip_size")
            except InvalidOperation:
                raise CommandError(f"Invalid pip size: {options['pip_size']}")

        if options["sell_on_stop"] is not None:
            task.sell_on_stop = options["sell_on_stop"] == "true"
            update_fields.append("sell_on_stop")

        if not update_fields:
            self.stdout.write("No fields to update.")
            return

        update_fields.append("updated_at")
        try:
            task.save(update_fields=update_fields)
        except Exception as e:
            raise CommandError(f"Failed to update: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated trading task: {task.pk} '{task.name}' (fields: {', '.join(update_fields)})"
            )
        )
