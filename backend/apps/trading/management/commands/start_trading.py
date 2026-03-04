"""Management command to start a trading task."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import TradingTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Start a trading task."""

    help = "Start a trading task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Trading task UUID")

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

        service = TaskService()
        try:
            task = service.start_task(task)
        except (ValueError, RuntimeError) as e:
            raise CommandError(str(e))

        self.stdout.write(
            self.style.SUCCESS(f"Started trading task: {task.pk} '{task.name}' -> {task.status}")
        )
