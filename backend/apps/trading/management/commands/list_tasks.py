"""Management command to list all tasks."""

from django.core.management.base import BaseCommand

from apps.trading.models import BacktestTask, TradingTask


class Command(BaseCommand):
    """List all backtest and trading tasks."""

    help = "List all backtest and trading tasks"

    def handle(self, *args, **options):
        """Handle the command."""
        # List backtest tasks
        self.stdout.write(self.style.SUCCESS("\n=== Backtest Tasks ==="))
        backtest_tasks = BacktestTask.objects.all().order_by("pk")
        if not backtest_tasks:
            self.stdout.write("  (none)")
        for task in backtest_tasks:
            self.stdout.write(
                f"  #{task.pk}: {task.name} - {task.status} (started: {task.started_at or 'never'})"
            )

        # List trading tasks
        self.stdout.write(self.style.SUCCESS("\n=== Trading Tasks ==="))
        trading_tasks = TradingTask.objects.all().order_by("pk")
        if not trading_tasks:
            self.stdout.write("  (none)")
        for task in trading_tasks:
            self.stdout.write(
                f"  #{task.pk}: {task.name} - {task.status} (started: {task.started_at or 'never'})"
            )

        self.stdout.write("")
