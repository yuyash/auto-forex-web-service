"""Management command to cleanup stuck tasks."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, TradingTask


class Command(BaseCommand):
    help = "Cleanup tasks stuck in STARTING or RUNNING status"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=120,
            help="Minutes before considering a task stuck (default: 120)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        timeout_minutes = options["timeout"]
        dry_run = options["dry_run"]
        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)

        self.stdout.write(f"Looking for tasks stuck for more than {timeout_minutes} minutes...")

        # Find stuck backtest tasks
        stuck_backtests = BacktestTask.objects.filter(
            status__in=[TaskStatus.STARTING, TaskStatus.RUNNING],
            updated_at__lt=cutoff_time,
        )

        # Find stuck trading tasks
        stuck_trading = TradingTask.objects.filter(
            status__in=[TaskStatus.STARTING, TaskStatus.RUNNING],
            updated_at__lt=cutoff_time,
        )

        total_stuck = stuck_backtests.count() + stuck_trading.count()

        if total_stuck == 0:
            self.stdout.write(self.style.SUCCESS("No stuck tasks found"))
            return

        self.stdout.write(f"Found {total_stuck} stuck task(s)")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            for task in stuck_backtests:
                self.stdout.write(
                    f"  Would reset BacktestTask {task.pk} (status={task.status}, "
                    f"updated_at={task.updated_at})"
                )
            for task in stuck_trading:
                self.stdout.write(
                    f"  Would reset TradingTask {task.pk} (status={task.status}, "
                    f"updated_at={task.updated_at})"
                )
        else:
            # Reset stuck tasks
            backtest_count = stuck_backtests.update(
                status=TaskStatus.FAILED,
                error_message=f"Task was stuck in {TaskStatus.STARTING}/{TaskStatus.RUNNING} "
                f"status for more than {timeout_minutes} minutes",
            )

            trading_count = stuck_trading.update(
                status=TaskStatus.FAILED,
                error_message=f"Task was stuck in {TaskStatus.STARTING}/{TaskStatus.RUNNING} "
                f"status for more than {timeout_minutes} minutes",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Reset {backtest_count} backtest task(s) and {trading_count} trading task(s)"
                )
            )
