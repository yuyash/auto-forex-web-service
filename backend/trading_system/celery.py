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

# Configure task routes for resource-intensive tasks
# Backtesting tasks are routed to a dedicated queue with resource limits
app.conf.task_routes = {
    "trading.tasks.run_backtest_task": {
        "queue": "backtest",
        "routing_key": "backtest",
    },
}

# Configure task annotations for resource limits
# These limits are enforced at the Celery worker level
app.conf.task_annotations = {
    "trading.tasks.run_backtest_task": {
        "time_limit": 3600,  # 1 hour hard limit
        "soft_time_limit": 3300,  # 55 minutes soft limit
        "rate_limit": "5/m",  # Max 5 backtests per minute
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    """Debug task for testing Celery configuration."""
    return f"Request: {self.request!r}"
