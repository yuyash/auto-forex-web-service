"""Celery configuration for the project.

This is intentionally minimal: tasks are discovered from installed Django apps.
"""

import logging
import os

from celery import Celery
from celery.signals import worker_ready
from django.apps import apps

logger = logging.getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("auto_forex")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
# Use a callable to ensure Django apps are loaded before discovery
app.autodiscover_tasks(lambda: [app_config.name for app_config in apps.get_app_configs()])


@worker_ready.connect
def _recover_orphaned_tasks_on_startup(**_kwargs: object) -> None:
    """Recover tasks that were orphaned by a previous crash (方法1).

    Runs with a short countdown to let Django fully initialise and to give
    the database connection pool time to warm up.
    """
    from apps.trading.tasks.recovery import recover_orphaned_tasks_beat

    try:
        recover_orphaned_tasks_beat.apply_async(countdown=10, queue="trading")
    except Exception:
        logger.exception("Failed to schedule orphaned task recovery on worker startup")


@worker_ready.connect
def _start_market_tick_supervisor(**_kwargs: object) -> None:
    # Only start the long-running market pub/sub supervisor in a worker that is
    # explicitly dedicated to the market queue. This prevents it from consuming
    # all concurrency and starving trading/backtest executions.
    if str(os.getenv("CELERY_START_MARKET_TICK_SUPERVISOR", "0")).strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    # Import lazily to avoid any Django setup ordering issues.
    try:
        from apps.market.tasks import ensure_tick_pubsub_running

        # Route to the market queue explicitly (also covered by CELERY_TASK_ROUTES).
        ensure_tick_pubsub_running.apply_async(countdown=5, queue="market")
    except Exception:
        # Avoid blocking worker startup.
        return
