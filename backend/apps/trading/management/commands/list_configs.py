"""Management command to list strategy configurations."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.trading.models import StrategyConfiguration


class Command(BaseCommand):
    """List strategy configurations."""

    help = "List strategy configurations"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("--email", type=str, default=None, help="Filter by user email")
        parser.add_argument(
            "--strategy-type", type=str, default=None, help="Filter by strategy type"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        qs = StrategyConfiguration.objects.select_related("user").order_by("-created_at")

        if options["email"]:
            try:
                user = User.objects.get(email=options["email"])
                qs = qs.filter(user=user)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User '{options['email']}' not found"))
                return

        if options["strategy_type"]:
            qs = qs.filter(strategy_type=options["strategy_type"])

        configs = list(qs)
        if not configs:
            self.stdout.write("No strategy configurations found.")
            return

        self.stdout.write(self.style.SUCCESS(f"\n=== Strategy Configurations ({len(configs)}) ==="))
        for c in configs:
            in_use = "in-use" if c.is_in_use() else "unused"
            self.stdout.write(
                f"  {c.pk}  {c.name:<30s}  type={c.strategy_type:<10s}  "
                f"user={c.user.email}  {in_use}"
            )
        self.stdout.write("")
