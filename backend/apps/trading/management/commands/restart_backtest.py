"""Management command to restart a backtest task."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import BacktestTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Restart a backtest task."""

    help = "Restart a backtest task by ID (clears execution data and re-runs)"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Backtest task UUID")

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
            task = service.restart_task(task_id)
        except (ValueError, RuntimeError) as e:
            raise CommandError(str(e))

        self.stdout.write(
            self.style.SUCCESS(f"Restarted backtest task: {task.pk} '{task.name}' -> {task.status}")
        )
