"""Management command to stop a running task."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.trading.models import BacktestTasks, CeleryTaskStatus, TradingTasks


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
            "--force",
            action="store_true",
            help="Force stop even if not running",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        task_type = options["task_type"]
        task_id = options["task_id"]
        force = options["force"]

        # Get the task
        if task_type == "backtest":
            model = BacktestTasks
            task_name = "trading.tasks.run_backtest_task"
        else:
            model = TradingTasks
            task_name = "trading.tasks.run_trading_task"

        try:
            task = model.objects.get(pk=task_id)
        except model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ {task_type.title()} task #{task_id} not found"))
            return

        # Check if task is running
        if task.status != "running" and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Task is not running (status: {task.status}). Use --force to stop anyway."
                )
            )
            return

        self.stdout.write(f"Stopping {task_type} task #{task_id} ({task.name})...")

        # Set stop flag in CeleryTaskStatus
        celery_status = CeleryTaskStatus.objects.filter(
            task_name=task_name, instance_key=str(task_id)
        ).first()

        if celery_status:
            celery_status.status = CeleryTaskStatus.Status.STOP_REQUESTED
            celery_status.status_message = "stop_requested via management command"
            celery_status.last_heartbeat_at = timezone.now()
            celery_status.save()
            self.stdout.write("✓ Set CeleryTaskStatus.STOP_REQUESTED")

        # Revoke Celery task
        if task.celery_task_id:
            result = task.get_celery_result()
            if result:
                result.revoke(terminate=True)
                self.stdout.write(f"✓ Revoked Celery task {task.celery_task_id}")

        # Update task status
        task.status = "stopped"
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        self.stdout.write("✓ Updated task status to STOPPED")

        self.stdout.write(self.style.SUCCESS(f"\n✅ Task #{task_id} stopped successfully"))
