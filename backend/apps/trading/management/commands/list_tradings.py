"""Management command to list trading tasks."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.trading.models import TradingTask


class Command(BaseCommand):
    """List trading tasks."""

    help = "List trading tasks"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("--email", type=str, default=None, help="Filter by user email")
        parser.add_argument("--status", type=str, default=None, help="Filter by status")

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        qs = TradingTask.objects.select_related("config", "user", "oanda_account").order_by(
            "-created_at"
        )

        if options["email"]:
            try:
                user = User.objects.get(email=options["email"])
                qs = qs.filter(user=user)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User '{options['email']}' not found"))
                return

        if options["status"]:
            qs = qs.filter(status=options["status"])

        tasks = list(qs)
        if not tasks:
            self.stdout.write("No trading tasks found.")
            return

        self.stdout.write(self.style.SUCCESS(f"\n=== Trading Tasks ({len(tasks)}) ==="))
        for t in tasks:
            self.stdout.write(
                f"  {t.pk}  {t.name:<30s}  status={t.status:<10s}  "
                f"config={t.config.name}  account={t.oanda_account.account_id}  "
                f"instrument={t.instrument}  user={t.user.email}  started={t.started_at or '-'}"
            )
        self.stdout.write("")
