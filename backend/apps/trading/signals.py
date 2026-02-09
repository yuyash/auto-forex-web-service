"""Signal handlers for trading app."""

import logging

from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.trading.enums import TaskStatus

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def reset_orphaned_tasks(sender, **kwargs):
    """
    Reset orphaned tasks on application startup.

    When the Django server restarts, any tasks that were in RUNNING, STARTING,
    or STOPPING state are orphaned (no longer have active Celery workers).
    This handler resets them to STOPPED state.

    This runs after migrations are applied, ensuring the database is ready.
    """
    # Only run for the trading app
    if sender.name != "apps.trading":
        return

    # Import here to avoid circular imports
    # pylint: disable=import-outside-toplevel
    from apps.trading.models import BacktestTask, TradingTask

    # Define orphaned states - tasks that require active workers
    orphaned_states = [
        TaskStatus.STARTING,
        TaskStatus.RUNNING,
        TaskStatus.STOPPING,
    ]

    # Reset orphaned backtest tasks
    orphaned_backtest_count = BacktestTask.objects.filter(status__in=orphaned_states).count()

    if orphaned_backtest_count > 0:
        BacktestTask.objects.filter(status__in=orphaned_states).update(
            status=TaskStatus.STOPPED,
            celery_task_id=None,
            error_message="Task was interrupted by server restart",
        )
        logger.warning(
            f"Reset {orphaned_backtest_count} orphaned backtest task(s) to STOPPED state"
        )

    # Reset orphaned trading tasks
    orphaned_trading_count = TradingTask.objects.filter(status__in=orphaned_states).count()

    if orphaned_trading_count > 0:
        TradingTask.objects.filter(status__in=orphaned_states).update(
            status=TaskStatus.STOPPED,
            celery_task_id=None,
            error_message="Task was interrupted by server restart",
        )
        logger.warning(f"Reset {orphaned_trading_count} orphaned trading task(s) to STOPPED state")

    # Log if no orphaned tasks found
    if orphaned_backtest_count == 0 and orphaned_trading_count == 0:
        logger.info("No orphaned tasks found on startup")
