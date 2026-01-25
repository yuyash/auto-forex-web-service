"""Status synchronization utilities for task models.

This module provides utilities for synchronizing task status between:
- Task models (BacktestTasks, TradingTasks)
- CeleryTaskStatus (execution tracking)
- Celery AsyncResult (actual Celery state)
"""

from __future__ import annotations

from logging import Logger, getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from celery.result import AsyncResult

    from apps.trading.enums import TaskStatus
    from apps.trading.models import BacktestTasks, TradingTasks

logger: Logger = getLogger(__name__)


def sync_task_status_from_celery(
    task: BacktestTasks | TradingTasks,
    celery_result: AsyncResult | None,
) -> None:
    """Synchronize task status with Celery task state.

    This function prioritizes CeleryTaskStatus over Celery AsyncResult to prevent
    race conditions during graceful stop operations.

    Priority order:
    1. Terminal states (STOPPED, COMPLETED, FAILED, PAUSED) - never overwrite
    2. CeleryTaskStatus.STOP_REQUESTED - don't overwrite during stop
    3. CeleryTaskStatus state - use if available
    4. Celery AsyncResult state - fallback

    Args:
        task: Task instance to synchronize
        celery_result: Celery AsyncResult for the task (optional)
    """
    from apps.trading.enums import TaskStatus
    from apps.trading.models import BacktestTasks, CeleryTaskStatus

    # Don't sync if task is already in a terminal or transitioning state
    # This prevents race conditions where async stop has updated DB but Celery hasn't caught up
    if task.status in [
        TaskStatus.STOPPED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.PAUSED,
    ]:
        logger.debug(
            "Skipping status sync - task in terminal/transitioning state",
            extra={"task_id": task.pk, "status": task.status},
        )
        return

    # Determine task name based on task type
    task_name = (
        "trading.tasks.run_backtest_task"
        if isinstance(task, BacktestTasks)
        else "trading.tasks.run_trading_task"
    )

    # Check CeleryTaskStatus first - it has priority over Celery AsyncResult
    # This prevents overwriting status during graceful stop operations
    celery_status = CeleryTaskStatus.objects.filter(
        task_name=task_name, instance_key=str(task.pk)
    ).first()

    if celery_status:
        logger.debug(
            "Found CeleryTaskStatus",
            extra={
                "task_id": task.pk,
                "celery_status": celery_status.status,
                "task_status": task.status,
            },
        )

        # If stop is requested, don't overwrite status
        if celery_status.status == CeleryTaskStatus.Status.STOP_REQUESTED:
            logger.debug(
                "Skipping status sync - stop requested",
                extra={"task_id": task.pk},
            )
            return

        # If CeleryTaskStatus shows stopped, sync to STOPPED
        if celery_status.status == CeleryTaskStatus.Status.STOPPED:
            if task.status != TaskStatus.STOPPED:
                logger.info(
                    "Syncing status to STOPPED from CeleryTaskStatus",
                    extra={"task_id": task.pk, "old_status": task.status},
                )
                task.status = TaskStatus.STOPPED
                task.save(update_fields=["status", "updated_at"])
            return

        # If CeleryTaskStatus shows failed, sync to FAILED
        if celery_status.status == CeleryTaskStatus.Status.FAILED:
            if task.status != TaskStatus.FAILED:
                logger.info(
                    "Syncing status to FAILED from CeleryTaskStatus",
                    extra={"task_id": task.pk, "old_status": task.status},
                )
                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
            return

        # If CeleryTaskStatus shows completed, sync to COMPLETED
        if celery_status.status == CeleryTaskStatus.Status.COMPLETED:
            if task.status != TaskStatus.COMPLETED:
                logger.info(
                    "Syncing status to COMPLETED from CeleryTaskStatus",
                    extra={"task_id": task.pk, "old_status": task.status},
                )
                task.status = TaskStatus.COMPLETED
                task.save(update_fields=["status", "updated_at"])
            return

    # Then check Celery AsyncResult as fallback
    if celery_result:
        logger.debug(
            "Checking Celery AsyncResult",
            extra={"task_id": task.pk, "celery_state": celery_result.state},
        )

        # Map Celery states to Task statuses
        celery_to_task_status: dict[str, TaskStatus] = {
            "PENDING": TaskStatus.CREATED,
            "STARTED": TaskStatus.RUNNING,
            "SUCCESS": TaskStatus.COMPLETED,
            "FAILURE": TaskStatus.FAILED,
            "REVOKED": TaskStatus.STOPPED,
        }

        new_status = celery_to_task_status.get(celery_result.state, task.status)
        if new_status != task.status:
            logger.info(
                "Syncing status from Celery AsyncResult",
                extra={
                    "task_id": task.pk,
                    "old_status": task.status,
                    "new_status": new_status,
                    "celery_state": celery_result.state,
                },
            )
            task.status = new_status
            task.save(update_fields=["status", "updated_at"])
    else:
        logger.debug(
            "No Celery AsyncResult available",
            extra={"task_id": task.pk},
        )
