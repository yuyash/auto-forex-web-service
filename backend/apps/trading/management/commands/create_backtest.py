"""Management command to create a backtest task."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.trading.enums import DataSource
from apps.trading.models import BacktestTask, StrategyConfiguration


class Command(BaseCommand):
    """Create a new backtest task."""

    help = "Create a new backtest task"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("--name", type=str, required=True, help="Task name")
        parser.add_argument("--email", type=str, required=True, help="User email")
        parser.add_argument(
            "--config-name", type=str, required=True, help="Strategy configuration name"
        )
        parser.add_argument(
            "--start-time",
            type=str,
            required=True,
            help="Backtest start time (ISO 8601, e.g. 2024-01-01T00:00:00Z)",
        )
        parser.add_argument(
            "--end-time",
            type=str,
            required=True,
            help="Backtest end time (ISO 8601, e.g. 2024-12-31T23:59:59Z)",
        )
        parser.add_argument("--description", type=str, default="", help="Task description")
        parser.add_argument(
            "--data-source",
            type=str,
            default="postgresql",
            choices=[c.value for c in DataSource],
            help="Data source (default: postgresql)",
        )
        parser.add_argument("--instrument", type=str, default="USD_JPY", help="Instrument")
        parser.add_argument(
            "--initial-balance", type=str, default="10000", help="Initial balance (default: 10000)"
        )
        parser.add_argument(
            "--account-currency", type=str, default="USD", help="Account currency (default: USD)"
        )
        parser.add_argument(
            "--commission", type=str, default="0", help="Commission per trade (default: 0)"
        )
        parser.add_argument("--pip-size", type=str, default=None, help="Pip size (e.g. 0.01)")

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            user = User.objects.get(email=options["email"])
        except User.DoesNotExist:
            raise CommandError(f"User with email '{options['email']}' not found")

        try:
            config = StrategyConfiguration.objects.get(user=user, name=options["config_name"])
        except StrategyConfiguration.DoesNotExist:
            raise CommandError(
                f"Strategy configuration '{options['config_name']}' not found for user"
            )

        start_time = parse_datetime(options["start_time"])
        if not start_time:
            raise CommandError(f"Invalid start time: {options['start_time']}")

        end_time = parse_datetime(options["end_time"])
        if not end_time:
            raise CommandError(f"Invalid end time: {options['end_time']}")

        try:
            initial_balance = Decimal(options["initial_balance"])
            commission = Decimal(options["commission"])
        except InvalidOperation as e:
            raise CommandError(f"Invalid decimal value: {e}")

        kwargs: dict[str, Any] = {
            "name": options["name"],
            "user": user,
            "config": config,
            "description": options["description"],
            "data_source": options["data_source"],
            "start_time": start_time,
            "end_time": end_time,
            "instrument": options["instrument"],
            "initial_balance": initial_balance,
            "account_currency": options["account_currency"],
            "commission_per_trade": commission,
        }
        if options["pip_size"]:
            try:
                kwargs["pip_size"] = Decimal(options["pip_size"])
            except InvalidOperation:
                raise CommandError(f"Invalid pip size: {options['pip_size']}")

        try:
            task = BacktestTask.objects.create(**kwargs)
        except Exception as e:
            raise CommandError(f"Failed to create backtest task: {e}")

        self.stdout.write(self.style.SUCCESS(f"Created backtest task: {task.pk} '{task.name}'"))
