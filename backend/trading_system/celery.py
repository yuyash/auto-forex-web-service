"""
Celery configuration for trading_system project.

This module configures Celery for asynchronous task processing with
resource limits for backtesting tasks.

Requirements: 12.2, 12.3
"""

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trading_system.settings")

app = Celery("trading_system")

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
        "time_limit": 259200,  # 72 hours hard limit (matches SystemSettings default)
        "soft_time_limit": 255600,  # 71 hours soft limit
        "rate_limit": "5/m",  # Max 5 backtests per minute
    },
    "trading.tasks.run_trading_task": {
        "time_limit": 259200,  # 72 hours hard limit (matches SystemSettings default)
        "soft_time_limit": 255600,  # 71 hours soft limit
    },
}

# Configure Celery Beat schedule for periodic tasks
# Note: The oanda-sync-task schedule is dynamically updated from SystemSettings
# The default value here is used only on first startup
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
    "oanda-sync-task": {
        "task": "trading.oanda_sync_task.oanda_sync_task",
        "schedule": 300.0,  # Default: Run every 5 minutes (configurable in System Settings)
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    """Debug task for testing Celery configuration."""
    return f"Request: {self.request!r}"
