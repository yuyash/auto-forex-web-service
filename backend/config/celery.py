"""Celery configuration for the project.

This is intentionally minimal: tasks are discovered from installed Django apps.
"""

import logging
import os

from celery import Celery
from celery.signals import (
    worker_ready,
    worker_shutting_down,
    worker_process_shutdown,
    task_failure,
    task_revoked,
)
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

# Also discover infrastructure tasks in config.tasks
app.autodiscover_tasks(["config"])


@worker_ready.connect
def _recover_orphaned_tasks_on_startup(**_kwargs: object) -> None:
    """Recover tasks that were orphaned by a previous crash (方法1).

    Runs with a short countdown to let Django fully initialise and to give
    the database connection pool time to warm up.
    """
    if str(os.getenv("CELERY_ENABLE_STARTUP_RECOVERY", "0")).strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    from apps.trading.tasks.recovery import recover_orphaned_tasks_startup

    try:
        recover_orphaned_tasks_startup.apply_async(countdown=10, queue="system")
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

        # Route to the system queue explicitly (also covered by CELERY_TASK_ROUTES).
        ensure_tick_pubsub_running.apply_async(countdown=5, queue="system")
    except Exception:
        # Avoid blocking worker startup.
        return


@worker_shutting_down.connect
def _log_worker_shutdown(sig: str = "unknown", how: str = "unknown", **kwargs: object) -> None:
    """Log when the Celery worker main process begins shutting down."""
    logger.warning(
        "Celery worker shutting down: sig=%s, how=%s, kwargs=%s",
        sig,
        how,
        {k: str(v) for k, v in kwargs.items()},
    )


@worker_process_shutdown.connect
def _log_worker_process_shutdown(pid: int = 0, exitcode: int = 0, **kwargs: object) -> None:
    """Log when a Celery worker child process exits."""
    logger.warning(
        "Celery worker process shutdown: pid=%s, exitcode=%s, kwargs=%s",
        pid,
        exitcode,
        {k: str(v) for k, v in kwargs.items()},
    )


@task_failure.connect
def _log_task_failure(
    task_id: str = "",
    exception: BaseException | None = None,
    traceback: object = None,
    sender: object = None,
    **kwargs: object,
) -> None:
    """Log task failures with exception details."""
    task_name = getattr(sender, "name", "unknown") if sender else "unknown"
    logger.error(
        "Celery task failed: task_id=%s, task=%s, exception=%s",
        task_id,
        task_name,
        exception,
    )


@task_revoked.connect
def _log_task_revoked(
    request: object = None,
    terminated: bool = False,
    signum: object = None,
    expired: bool = False,
    **kwargs: object,
) -> None:
    """Log when a task is revoked or terminated."""
    task_id = getattr(request, "id", "unknown") if request else "unknown"
    task_name = getattr(request, "task", "unknown") if request else "unknown"
    logger.warning(
        "Celery task revoked: task_id=%s, task=%s, terminated=%s, signum=%s, expired=%s",
        task_id,
        task_name,
        terminated,
        signum,
        expired,
    )
