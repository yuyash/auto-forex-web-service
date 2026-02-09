"""Management command to stop a running task."""

from uuid import UUID

from django.core.management.base import BaseCommand

from apps.trading.models import BacktestTask, TradingTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Stop a running backtest or trading task."""

    help = "Stop a running backtest or trading task"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "task_type",
            type=str,
            choices=["backtest", "trading"],
            help="Type of task (backtest or trading)",
        )
        parser.add_argument(
            "task_id",
            type=int,
            help="ID of the task to stop",
        )
        parser.add_argument(
            "--mode",
            type=str,
            choices=["immediate", "graceful", "graceful_close"],
            default="graceful",
            help="Stop mode (default: graceful)",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        task_type = options["task_type"]
        task_id = options["task_id"]
        mode = options["mode"]

        # Get the task
        if task_type == "backtest":
            model = BacktestTask
        else:
            model = TradingTask

        try:
            task = model.objects.get(pk=task_id)
        except model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ {task_type.title()} task #{task_id} not found"))
            return

        self.stdout.write(f"Stopping {task_type} task #{task_id} ({task.name})...")

        # Use TaskService to stop the task
        task_service = TaskService()
        try:
            success = task_service.stop_task(UUID(int=task_id), mode=mode)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ Task #{task_id} stop initiated (mode: {mode})")
                )
            else:
                self.stdout.write(self.style.ERROR(f"❌ Failed to stop task #{task_id}"))
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f"❌ {str(e)}"))
