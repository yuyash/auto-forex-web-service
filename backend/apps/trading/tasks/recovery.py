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
# orphaned. The value must remain comfortably larger than the heartbeat
# interval (5 s) to avoid false positives during normal execution, while
# recovering quickly after deployments that replace the worker containers.
ORPHAN_HEARTBEAT_THRESHOLD = timedelta(minutes=1)

# Statuses that indicate a task *should* be actively running.
_ACTIVE_STATUSES = [TaskStatus.RUNNING, TaskStatus.STARTING]

# Maximum number of orphaned tasks to process per recovery run to avoid
# unbounded memory usage if many tasks are stuck.
_MAX_RECOVERY_BATCH = 100


def _instance_key(task: BacktestTask | TradingTask) -> str:
    return f"{task.pk}:{task.execution_id}"


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

    # --- Backtest tasks (bounded queryset) ---
    orphaned_backtest = list(
        BacktestTask.objects.filter(
            status__in=_ACTIVE_STATUSES,
        ).order_by("started_at")[:_MAX_RECOVERY_BATCH]
    )
    backtest_heartbeats = _prefetch_heartbeats(orphaned_backtest, "trading.tasks.run_backtest_task")
    for task in orphaned_backtest:
        if not _is_orphaned_prefetched(task, backtest_heartbeats, cutoff):
            continue
        if _recover_task(task, TaskType.BACKTEST, service, source):
            counts["backtest"] += 1

    # --- Trading tasks (bounded queryset) ---
    orphaned_trading = list(
        TradingTask.objects.filter(
            status__in=_ACTIVE_STATUSES,
        ).order_by("started_at")[:_MAX_RECOVERY_BATCH]
    )
    trading_heartbeats = _prefetch_heartbeats(orphaned_trading, "trading.tasks.run_trading_task")
    for task in orphaned_trading:
        if not _is_orphaned_prefetched(task, trading_heartbeats, cutoff):
            continue
        if _recover_task(task, TaskType.TRADING, service, source):
            counts["trading"] += 1

    total = counts["backtest"] + counts["trading"]
    if total:
        logger.warning(
            "[RECOVERY:%s] Recovered %d orphaned task(s) (backtest=%d, trading=%d)",
            source,
            total,
            counts["backtest"],
            counts["trading"],
        )
    else:
        logger.info("[RECOVERY:%s] No orphaned tasks found", source)

    return counts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _prefetch_heartbeats(
    tasks: list[BacktestTask | TradingTask],
    celery_task_name: str,
) -> dict[str, CeleryTaskStatus]:
    """Fetch all CeleryTaskStatus rows for a batch of tasks in one query."""
    if not tasks:
        return {}
    keys = [_instance_key(t) for t in tasks]
    return {
        cts.instance_key: cts
        for cts in CeleryTaskStatus.objects.filter(
            task_name=celery_task_name,
            instance_key__in=keys,
        )
    }


def _is_orphaned_prefetched(
    task: BacktestTask | TradingTask,
    heartbeats: dict[str, CeleryTaskStatus],
    cutoff: datetime,
) -> bool:
    """Return True if the task has no recent heartbeat (using prefetched data)."""
    cts = heartbeats.get(_instance_key(task))

    if cts is None:
        logger.info(
            "[RECOVERY] No CeleryTaskStatus row for task_id=%s — treating as orphaned",
            task.pk,
        )
        return True

    if cts.last_heartbeat_at is None or cts.last_heartbeat_at < cutoff:
        logger.info(
            "[RECOVERY] Stale heartbeat for task_id=%s — last_heartbeat=%s, cutoff=%s",
            task.pk,
            cts.last_heartbeat_at,
            cutoff,
        )
        return True

    return False


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
        logger.info(
            "[RECOVERY] No CeleryTaskStatus row for task_id=%s (%s) — treating as orphaned",
            task.pk,
            celery_task_name,
        )
        return True

    if cts.last_heartbeat_at is None or cts.last_heartbeat_at < cutoff:
        logger.info(
            "[RECOVERY] Stale heartbeat for task_id=%s (%s) — last_heartbeat=%s, cutoff=%s",
            task.pk,
            celery_task_name,
            cts.last_heartbeat_at,
            cutoff,
        )
        return True

    return False


def _recover_task(
    task: BacktestTask | TradingTask,
    task_type: TaskType,
    service: Any,
    source: str,
) -> bool:
    """Reset an orphaned task to CREATED and re-submit it."""
    logger.warning(
        "[RECOVERY:%s] Recovering orphaned task - task_id=%s, type=%s, "
        "old_status=%s, execution_id=%s",
        source,
        task.pk,
        task_type,
        task.status,
        task.execution_id,
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
        execution_id=None,
        started_at=None,
        completed_at=None,
        error_message=None,
        error_traceback=None,
    )

    if rows == 0:
        logger.info("[RECOVERY:%s] Task already transitioned - task_id=%s", source, task.pk)
        return False

    CeleryTaskStatus.objects.filter(
        task_name="trading.tasks.run_backtest_task",
        instance_key=_instance_key(task),
    ).delete()

    TaskLog.objects.create(
        task_type=task_type,
        task_id=task.pk,
        execution_id=task.execution_id,
        level="WARNING",
        component=__name__,
        message=(
            f"Backtest task recovered from orphaned {task.status} state "
            f"(source={source}). The previous partial run was discarded and the "
            "backtest is restarting from the beginning."
        ),
    )

    task.refresh_from_db()
    try:
        service.start_task(task)
        logger.info("[RECOVERY:%s] Task re-submitted - task_id=%s", source, task.pk)
        return True
    except Exception:
        logger.exception("[RECOVERY:%s] Failed to re-submit task - task_id=%s", source, task.pk)
        model_class.objects.filter(pk=task.pk).update(
            status=TaskStatus.FAILED,
            error_message=f"Recovery failed after crash (source={source})",
        )
        return False


def _recover_trading_task(*, task: BacktestTask | TradingTask, service: Any, source: str) -> bool:
    """Resume an orphaned trading task in the same execution run."""
    # Optimistic lock: verify the task is still in a recoverable state before
    # proceeding.  Without this, concurrent recovery runs could both attempt
    # to resume the same task.
    rows = TradingTask.objects.filter(
        pk=task.pk,
        status__in=_ACTIVE_STATUSES,
    ).update(status=TaskStatus.STARTING)
    if rows == 0:
        logger.info("[RECOVERY:%s] Trading task already transitioned - task_id=%s", source, task.pk)
        return False

    CeleryTaskStatus.objects.filter(
        task_name="trading.tasks.run_trading_task",
        instance_key=_instance_key(task),
    ).delete()

    TaskLog.objects.create(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_id=task.execution_id,
        level="WARNING",
        component=__name__,
        message=(
            f"Trading task recovered from orphaned {task.status} state "
            f"(source={source}). Resuming the same execution run with the "
            "persisted strategy and grid state."
        ),
    )

    try:
        service.recover_trading_task(task)
        logger.info(
            "[RECOVERY:%s] Trading task resumed in same run - task_id=%s, execution_id=%s",
            source,
            task.pk,
            task.execution_id,
        )
        return True
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
        return False


# ---------------------------------------------------------------------------
# Celery Beat task
# ---------------------------------------------------------------------------


@shared_task(name="trading.tasks.recover_orphaned_tasks")
def recover_orphaned_tasks_beat() -> dict[str, int]:
    """Periodic Celery Beat task to detect and recover orphaned tasks."""
    return recover_orphaned_tasks(source="celery_beat")
