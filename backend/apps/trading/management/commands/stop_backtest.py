"""Management command to stop a backtest task."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import BacktestTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Stop a running backtest task."""

    help = "Stop a running backtest task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Backtest task UUID")
        parser.add_argument(
            "--mode",
            type=str,
            default="graceful",
            choices=["immediate", "graceful"],
            help="Stop mode (default: graceful)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            task_id = UUID(options["task_id"])
        except ValueError:
            raise CommandError(f"Invalid UUID: {options['task_id']}")

        try:
            BacktestTask.objects.get(pk=task_id)
        except BacktestTask.DoesNotExist:
            raise CommandError(f"Backtest task '{task_id}' not found")

        service = TaskService()
        try:
            service.stop_task(task_id, mode=options["mode"])
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"Stop initiated for backtest task: {task_id}"))
