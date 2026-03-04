"""Management command to update a backtest task."""

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.trading.enums import DataSource
from apps.trading.models import BacktestTask, StrategyConfiguration


class Command(BaseCommand):
    """Update a backtest task."""

    help = "Update a backtest task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Backtest task UUID")
        parser.add_argument("--name", type=str, default=None, help="New task name")
        parser.add_argument("--description", type=str, default=None, help="New description")
        parser.add_argument("--config-name", type=str, default=None, help="New config name")
        parser.add_argument("--start-time", type=str, default=None, help="New start time (ISO)")
        parser.add_argument("--end-time", type=str, default=None, help="New end time (ISO)")
        parser.add_argument("--instrument", type=str, default=None, help="New instrument")
        parser.add_argument(
            "--data-source",
            type=str,
            default=None,
            choices=[c.value for c in DataSource],
        )
        parser.add_argument("--initial-balance", type=str, default=None)
        parser.add_argument("--commission", type=str, default=None)
        parser.add_argument("--pip-size", type=str, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            task_id = UUID(options["task_id"])
        except ValueError:
            raise CommandError(f"Invalid UUID: {options['task_id']}")

        try:
            task = BacktestTask.objects.get(pk=task_id)
        except BacktestTask.DoesNotExist:
            raise CommandError(f"Backtest task '{task_id}' not found")

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

        if options["start_time"] is not None:
            dt = parse_datetime(options["start_time"])
            if not dt:
                raise CommandError(f"Invalid start time: {options['start_time']}")
            task.start_time = dt
            update_fields.append("start_time")

        if options["end_time"] is not None:
            dt = parse_datetime(options["end_time"])
            if not dt:
                raise CommandError(f"Invalid end time: {options['end_time']}")
            task.end_time = dt
            update_fields.append("end_time")

        if options["instrument"] is not None:
            task.instrument = options["instrument"]
            update_fields.append("instrument")

        if options["data_source"] is not None:
            task.data_source = options["data_source"]
            update_fields.append("data_source")

        if options["initial_balance"] is not None:
            try:
                task.initial_balance = Decimal(options["initial_balance"])
                update_fields.append("initial_balance")
            except InvalidOperation:
                raise CommandError(f"Invalid initial balance: {options['initial_balance']}")

        if options["commission"] is not None:
            try:
                task.commission_per_trade = Decimal(options["commission"])
                update_fields.append("commission_per_trade")
            except InvalidOperation:
                raise CommandError(f"Invalid commission: {options['commission']}")

        if options["pip_size"] is not None:
            try:
                task.pip_size = Decimal(options["pip_size"])
                update_fields.append("pip_size")
            except InvalidOperation:
                raise CommandError(f"Invalid pip size: {options['pip_size']}")

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
                f"Updated backtest task: {task.pk} '{task.name}' (fields: {', '.join(update_fields)})"
            )
        )
