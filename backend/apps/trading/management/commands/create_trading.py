"""Management command to create a trading task."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration, TradingTask


class Command(BaseCommand):
    """Create a new trading task."""

    help = "Create a new trading task"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("--name", type=str, required=True, help="Task name")
        parser.add_argument("--email", type=str, required=True, help="User email")
        parser.add_argument(
            "--config-name", type=str, required=True, help="Strategy configuration name"
        )
        parser.add_argument("--account-id", type=str, required=True, help="OANDA account ID")
        parser.add_argument("--description", type=str, default="", help="Task description")
        parser.add_argument("--instrument", type=str, default="USD_JPY", help="Instrument")
        parser.add_argument("--pip-size", type=str, default=None, help="Pip size")
        parser.add_argument(
            "--sell-on-stop",
            action="store_true",
            help="Close positions when task is stopped",
        )

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

        try:
            oanda_account = OandaAccounts.objects.get(user=user, account_id=options["account_id"])
        except OandaAccounts.DoesNotExist:
            raise CommandError(f"OANDA account '{options['account_id']}' not found for user")

        kwargs: dict[str, Any] = {
            "name": options["name"],
            "user": user,
            "config": config,
            "oanda_account": oanda_account,
            "description": options["description"],
            "instrument": options["instrument"],
            "sell_on_stop": options["sell_on_stop"],
        }
        if options["pip_size"]:
            try:
                kwargs["pip_size"] = Decimal(options["pip_size"])
            except InvalidOperation:
                raise CommandError(f"Invalid pip size: {options['pip_size']}")

        try:
            task = TradingTask.objects.create(**kwargs)
        except Exception as e:
            raise CommandError(f"Failed to create trading task: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Created trading task: {task.pk} '{task.name}' "
                f"(account={oanda_account.account_id})"
            )
        )
