"""Signal handlers for trading app."""

import logging

logger = logging.getLogger(__name__)


def reset_orphaned_tasks(sender, **kwargs):
    """Legacy no-op kept for backward import compatibility.

    Orphan recovery is handled by ``trading.tasks.recovery`` via worker-ready
    and Celery Beat hooks. We intentionally do not mutate task states from a
    Django ``post_migrate`` signal anymore.
    """
    _ = sender
    _ = kwargs
    logger.info("reset_orphaned_tasks signal handler is disabled; recovery task is authoritative")
