"""Orphaned task recovery for crash recovery and periodic health checks.

When the system crashes (e.g., worker killed, server power loss), tasks may
remain in RUNNING/STARTING status in the database with no Celery worker
actually processing them.  These "orphaned" tasks need to be detected and
re-queued so they can resume execution.

This module provides:
- ``recover_orphaned_tasks``: core recovery logic (shared by startup & beat)
- ``recover_orphaned_tasks_beat``: Celery task for periodic invocation
- ``on_worker_ready``: signal handler for startup-time recovery
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTask, TaskLog, TradingTask
from apps.trading.models.celery import CeleryTaskStatus

logger = logging.getLogger(__name__)

# A task whose last heartbeat is older than this threshold is considered
# orphaned.  The value must be comfortably larger than the heartbeat
# interval (5 s) to avoid false positives during normal execution.
ORPHAN_HEARTBEAT_THRESHOLD = timedelta(minutes=5)

# Statuses that indicate a task *should* be actively running.
_ACTIVE_STATUSES = [TaskStatus.RUNNING, TaskStatus.STARTING]


def _instance_key(task: BacktestTask | TradingTask) -> str:
    return f"{task.pk}:{int(getattr(task, 'execution_run_id', 0) or 0)}"


def recover_orphaned_tasks(*, source: str = "manual") -> dict[str, int]:
    """Detect and re-queue orphaned backtest and trading tasks.

    A task is considered orphaned when:
    1. Its DB status is RUNNING or STARTING, **and**
    2. Its ``CeleryTaskStatus.last_heartbeat_at`` is older than
       ``ORPHAN_HEARTBEAT_THRESHOLD``, **or** no ``CeleryTaskStatus`` row
       exists at all.

    Backtest tasks are reset to CREATED and re-submitted via
    ``TaskService.start_task``.
    Trading tasks are resumed in the same execution run via
    ``TaskService.recover_trading_task``.

    Args:
        source: Label for log messages (e.g. "worker_ready", "celery_beat").

    Returns:
        Dict with counts: ``{"backtest": N, "trading": N}``
    """
    from apps.trading.tasks.service import TaskService

    cutoff = dj_timezone.now() - ORPHAN_HEARTBEAT_THRESHOLD
    service = TaskService()
    counts: dict[str, int] = {"backtest": 0, "trading": 0}

    # --- Backtest tasks ---
    orphaned_backtest = BacktestTask.objects.filter(status__in=_ACTIVE_STATUSES)
    for task in orphaned_backtest:
        if not _is_orphaned(task, "trading.tasks.run_backtest_task", cutoff):
            continue
        if _recover_task(task, TaskType.BACKTEST, service, source):
            counts["backtest"] += 1

    # --- Trading tasks ---
    orphaned_trading = TradingTask.objects.filter(status__in=_ACTIVE_STATUSES)
    for task in orphaned_trading:
        if not _is_orphaned(task, "trading.tasks.run_trading_task", cutoff):
            continue
        if _recover_task(task, TaskType.TRADING, service, source):
            counts["trading"] += 1

    total = counts["backtest"] + counts["trading"]
    if total:
        logger.warning(
            f"[RECOVERY:{source}] Recovered {total} orphaned task(s) "
            f"(backtest={counts['backtest']}, trading={counts['trading']})"
        )
    else:
        logger.info(f"[RECOVERY:{source}] No orphaned tasks found")

    return counts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_orphaned(
    task: BacktestTask | TradingTask,
    celery_task_name: str,
    cutoff: datetime,
) -> bool:
    """Return True if the task has no recent heartbeat."""
    cts = CeleryTaskStatus.objects.filter(
        task_name=celery_task_name,
        instance_key=_instance_key(task),
    ).first()

    if cts is None:
        # No tracking row at all — definitely orphaned.
        logger.info(
            f"[RECOVERY] No CeleryTaskStatus row for task_id={task.pk} "
            f"({celery_task_name}) — treating as orphaned"
        )
        return True

    if cts.last_heartbeat_at is None or cts.last_heartbeat_at < cutoff:
        logger.info(
            f"[RECOVERY] Stale heartbeat for task_id={task.pk} "
            f"({celery_task_name}) — last_heartbeat={cts.last_heartbeat_at}, "
            f"cutoff={cutoff}"
        )
        return True

    # Heartbeat is recent — task is still alive.
    return False


def _recover_task(
    task: BacktestTask | TradingTask,
    task_type: TaskType,
    service: Any,
    source: str,
) -> bool:
    """Reset an orphaned task to CREATED and re-submit it.

    Returns:
        True if the task was actually recovered, False if another process
        already handled it.
    """
    logger.warning(
        f"[RECOVERY:{source}] Recovering orphaned task - "
        f"task_id={task.pk}, type={task_type}, "
        f"old_status={task.status}, celery_task_id={task.celery_task_id}"
    )

    model_class = type(task)

    if task_type == TaskType.TRADING:
        return _recover_trading_task(task=task, service=service, source=source)

    # Backtest recovery: reset to CREATED and submit as a fresh run.
    rows = model_class.objects.filter(
        pk=task.pk,
        status__in=_ACTIVE_STATUSES,
    ).update(
        status=TaskStatus.CREATED,
        celery_task_id=None,
        started_at=None,
        completed_at=None,
        error_message=None,
        error_traceback=None,
    )

    if rows == 0:
        logger.info(f"[RECOVERY:{source}] Task already transitioned - task_id={task.pk}")
        return False

    CeleryTaskStatus.objects.filter(
        task_name="trading.tasks.run_backtest_task",
        instance_key=_instance_key(task),
    ).delete()

    TaskLog.objects.create(
        task_type=task_type,
        task_id=task.pk,
        execution_run_id=int(getattr(task, "execution_run_id", 0) or 0),
        level="WARNING",
        component=__name__,
        message=(
            f"Task recovered from orphaned {task.status} state "
            f"(source={source}). Re-queuing for execution."
        ),
    )

    task.refresh_from_db()
    try:
        service.start_task(task)
        logger.info(f"[RECOVERY:{source}] Task re-submitted - task_id={task.pk}")
    except Exception:
        logger.exception(f"[RECOVERY:{source}] Failed to re-submit task - task_id={task.pk}")
        model_class.objects.filter(pk=task.pk).update(
            status=TaskStatus.FAILED,
            error_message=f"Recovery failed after crash (source={source})",
        )

    return True


def _recover_trading_task(*, task: BacktestTask | TradingTask, service: Any, source: str) -> bool:
    """Resume an orphaned trading task in the same execution run."""
    # Ensure stale heartbeat rows from the dead worker do not affect the resumed run.
    CeleryTaskStatus.objects.filter(
        task_name="trading.tasks.run_trading_task",
        instance_key=_instance_key(task),
    ).delete()

    TaskLog.objects.create(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_run_id=int(getattr(task, "execution_run_id", 0) or 0),
        level="WARNING",
        component=__name__,
        message=(
            f"Trading task recovered from orphaned {task.status} state "
            f"(source={source}). Resuming same execution run."
        ),
    )

    try:
        service.recover_trading_task(task)
        logger.info(
            "[RECOVERY:%s] Trading task resumed in same run - task_id=%s, run=%s",
            source,
            task.pk,
            int(getattr(task, "execution_run_id", 0) or 0),
        )
    except Exception:
        logger.exception(
            "[RECOVERY:%s] Failed to resume trading task - task_id=%s",
            source,
            task.pk,
        )
        TradingTask.objects.filter(pk=task.pk).update(
            status=TaskStatus.FAILED,
            error_message=f"Recovery failed after crash (source={source})",
        )

    return True


# ---------------------------------------------------------------------------
# Celery Beat task (方法3)
# ---------------------------------------------------------------------------


@shared_task(name="trading.tasks.recover_orphaned_tasks")
def recover_orphaned_tasks_beat() -> dict[str, int]:
    """Periodic Celery Beat task to detect and recover orphaned tasks."""
    return recover_orphaned_tasks(source="celery_beat")
