"""Celery configuration for the project.

This is intentionally minimal: tasks are discovered from installed Django apps.
"""

import os

from celery import Celery
from celery.signals import worker_ready

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


@worker_ready.connect
def _start_market_tick_supervisor(**_kwargs: object) -> None:
    # Import lazily to avoid any Django setup ordering issues.
    try:
        from apps.market.tasks import ensure_tick_pubsub_running

        ensure_tick_pubsub_running.apply_async(countdown=5)
    except Exception:
        # Avoid blocking worker startup.
        return
