"""Management command to stop a trading task."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import TradingTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Stop a running trading task."""

    help = "Stop a running trading task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Trading task UUID")
        parser.add_argument(
            "--mode",
            type=str,
            default="graceful",
            choices=["immediate", "graceful", "graceful_close"],
            help="Stop mode (default: graceful)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        try:
            task_id = UUID(options["task_id"])
        except ValueError:
            raise CommandError(f"Invalid UUID: {options['task_id']}")

        try:
            TradingTask.objects.get(pk=task_id)
        except TradingTask.DoesNotExist:
            raise CommandError(f"Trading task '{task_id}' not found")

        service = TaskService()
        try:
            service.stop_task(task_id, mode=options["mode"])
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"Stop initiated for trading task: {task_id}"))
