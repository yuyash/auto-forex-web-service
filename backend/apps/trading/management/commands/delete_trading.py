"""Management command to delete a trading task."""

from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import TradingTask


class Command(BaseCommand):
    """Delete a trading task."""

    help = "Delete a trading task by ID"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument("task_id", type=str, help="Trading task UUID")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

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

        if not options["force"]:
            confirm = input(f"Delete trading task '{task.name}' (status={task.status})? [y/N] ")
            if confirm.lower() != "y":
                self.stdout.write("Cancelled.")
                return

        try:
            task.delete()
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"Deleted trading task: {task_id}"))
