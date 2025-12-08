"""
Celery configuration for auto_forex project.

This module configures Celery for asynchronous task processing with
resource limits for backtesting tasks.
"""

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("auto_forex")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure task annotations for resource limits
# These limits are enforced at the Celery worker level
app.conf.task_annotations = {
    "trading.tasks.run_backtest_task": {
        "time_limit": 259200,  # 72 hours hard limit
        "soft_time_limit": 255600,  # 71 hours soft limit
        "rate_limit": "5/m",  # Max 5 backtests per minute
    },
    "trading.tasks.run_trading_task": {
        "time_limit": 259200,  # 72 hours hard limit
        "soft_time_limit": 255600,  # 71 hours soft limit
    },
}

# Configure Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    "run-host-access-monitoring": {
        "task": "trading.tasks.run_host_access_monitoring",
        "schedule": 300.0,  # Run every 5 minutes (300 seconds)
    },
    "cleanup-old-tick-data": {
        "task": "trading.tasks.cleanup_old_tick_data",
        "schedule": 86400.0,  # Run daily (86400 seconds = 24 hours)
    },
    "cleanup-stale-locks": {
        "task": "trading.tasks.cleanup_stale_locks_task",
        "schedule": 60.0,  # Run every 1 minute (60 seconds)
    },
    "resume-running-trading-tasks": {
        "task": "trading.tasks.resume_running_trading_tasks",
        "schedule": 120.0,  # Run every 2 minutes to ensure trading tasks have streams
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    """Debug task for testing Celery configuration."""
    return f"Request: {self.request!r}"


# Signal to resume running trading tasks when worker is ready
@app.on_after_finalize.connect
def setup_startup_tasks(
    sender: Celery,  # pylint: disable=unused-argument
    **kwargs: object,
) -> None:
    """
    Schedule startup tasks after Celery app is fully configured.

    This signal fires after the app is fully configured and ready.
    We use a short delay to ensure the worker is fully operational
    before attempting to resume trading tasks.
    """
    # Import here to avoid circular imports
    from apps.tasks.tasks import resume_running_trading_tasks

    # Schedule the task to run 10 seconds after worker starts
    # This gives time for the worker to fully initialize
    # Use force_restart=True to clear stale cache entries from before the restart
    resume_running_trading_tasks.apply_async(kwargs={"force_restart": True}, countdown=10)
