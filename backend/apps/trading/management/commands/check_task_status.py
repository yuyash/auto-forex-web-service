"""Management command to check task status."""

from django.core.management.base import BaseCommand

from apps.trading.models import BacktestTasks, CeleryTaskStatus, TradingTasks


class Command(BaseCommand):
    """Check the status of a backtest or trading task."""

    help = "Check the status of a backtest or trading task"

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
            help="ID of the task to check",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        task_type = options["task_type"]
        task_id = options["task_id"]

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

        # Display task info
        self.stdout.write(self.style.SUCCESS(f"\n{task_type.title()} Task #{task.pk}"))
        self.stdout.write(f"Name: {task.name}")
        self.stdout.write(f"Status: {task.status}")
        self.stdout.write(f"Started at: {task.started_at}")
        self.stdout.write(f"Completed at: {task.completed_at}")
        self.stdout.write(f"Celery Task ID: {task.celery_task_id}")

        # Check CeleryTaskStatus
        celery_status = CeleryTaskStatus.objects.filter(
            task_name=task_name, instance_key=str(task.pk)
        ).first()

        if celery_status:
            self.stdout.write("\nCeleryTaskStatus:")
            self.stdout.write(f"  Status: {celery_status.status}")
            self.stdout.write(f"  Message: {celery_status.status_message}")
            self.stdout.write(f"  Last Heartbeat: {celery_status.last_heartbeat_at}")

        # Check Celery AsyncResult
        if task.celery_task_id:
            result = task.get_celery_result()
            if result:
                self.stdout.write("\nCelery AsyncResult:")
                self.stdout.write(f"  State: {result.state}")
                try:
                    self.stdout.write(f"  Info: {result.info}")
                except Exception:
                    pass

        # Status summary
        if task.status == "running":
            self.stdout.write(self.style.WARNING("\n⚠️  Task is RUNNING"))
        elif task.status == "stopped":
            self.stdout.write(self.style.SUCCESS("\n✅ Task is STOPPED"))
        elif task.status == "completed":
            self.stdout.write(self.style.SUCCESS("\n✅ Task is COMPLETED"))
        elif task.status == "failed":
            self.stdout.write(self.style.ERROR("\n❌ Task FAILED"))
            if task.error_message:
                self.stdout.write(f"Error: {task.error_message}")
        else:
            self.stdout.write(f"\nℹ️  Task is {task.status.upper()}")
