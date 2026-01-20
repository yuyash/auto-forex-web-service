"""
Monitoring tasks for detecting and handling stuck executions.

This module provides periodic tasks that monitor execution health and
automatically clean up stuck or orphaned tasks.
"""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTasks, Executions, TradingTasks

logger: Logger = getLogger(__name__)

# Timeout thresholds
EXECUTION_TIMEOUT_MINUTES = 60  # Consider stuck after 60 minutes with no updates
HEARTBEAT_CHECK_MINUTES = 5  # Check for stuck tasks every 5 minutes


@shared_task(name="trading.monitor_stuck_executions")
def monitor_stuck_executions() -> dict[str, Any]:
    """
    Monitor for stuck executions and mark them as failed.

    An execution is considered stuck if:
    1. Status is 'running' or 'queued'
    2. Started more than EXECUTION_TIMEOUT_MINUTES ago
    3. No Celery task is actively processing it

    Returns:
        Dictionary with monitoring results
    """
    logger.info("Starting stuck execution monitoring")

    timeout_threshold = timezone.now() - timedelta(minutes=EXECUTION_TIMEOUT_MINUTES)

    # Find potentially stuck executions
    stuck_executions = Executions.objects.filter(
        Q(status=TaskStatus.RUNNING) | Q(status=TaskStatus.CREATED),
        started_at__lt=timeout_threshold,
        completed_at__isnull=True,
    )

    results: dict[str, Any] = {
        "checked_at": timezone.now().isoformat(),
        "timeout_threshold": timeout_threshold.isoformat(),
        "stuck_count": 0,
        "cleaned_up": [],
        "errors": [],
    }

    for execution in stuck_executions:
        try:
            # Check if there's an active Celery task
            from celery import current_app

            active_tasks = current_app.control.inspect().active()
            is_active = False

            if active_tasks:
                for worker_tasks in active_tasks.values():
                    for task in worker_tasks:
                        # Check if this execution's Celery task is active
                        task_args = task.get("args", [])
                        if (
                            len(task_args) >= 2
                            and task_args[0] == execution.task_type
                            and task_args[1] == execution.task_id
                        ):
                            is_active = True
                            break
                    if is_active:
                        break

            if not is_active:
                # Mark execution as failed
                execution.status = TaskStatus.FAILED
                execution.completed_at = timezone.now()
                execution.error_message = (
                    f"Execution stuck - no active Celery task found. "
                    f"Started at {execution.started_at}, "
                    f"timeout threshold: {EXECUTION_TIMEOUT_MINUTES} minutes"
                )
                execution.save(update_fields=["status", "completed_at", "error_message"])

                # Update parent task status
                if execution.task_type == "backtest":
                    task = BacktestTasks.objects.get(id=execution.task_id)
                else:
                    task = TradingTasks.objects.get(id=execution.task_id)

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])

                results["stuck_count"] += 1
                results["cleaned_up"].append(
                    {
                        "execution_id": execution.id,
                        "task_type": execution.task_type,
                        "task_id": execution.task_id,
                        "started_at": execution.started_at.isoformat(),
                    }
                )

                logger.warning(
                    f"Cleaned up stuck execution: {execution.id} "
                    f"(task_type={execution.task_type}, task_id={execution.task_id})"
                )

        except Exception as e:
            error_msg = f"Error processing execution {execution.id}: {str(e)}"
            logger.exception(error_msg)
            results["errors"].append(error_msg)

    logger.info(
        f"Stuck execution monitoring complete. "
        f"Found and cleaned up {results['stuck_count']} stuck executions"
    )

    return results


@shared_task(name="trading.sync_celery_task_status")
def sync_celery_task_status() -> dict[str, Any]:
    """
    Sync execution status with Celery task status.

    Checks all running/queued executions and verifies they have
    corresponding active Celery tasks. Marks orphaned executions as failed.

    Returns:
        Dictionary with sync results
    """
    logger.info("Starting Celery task status sync")

    from celery import current_app

    # Get all active Celery tasks
    active_tasks = current_app.control.inspect().active()
    active_execution_ids = set()

    if active_tasks:
        for worker_tasks in active_tasks.values():
            for task in worker_tasks:
                # Extract execution info from task args
                task_args = task.get("args", [])
                if len(task_args) >= 2:
                    task_type = task_args[0]
                    task_id = task_args[1]
                    # Find corresponding execution
                    try:
                        execution = Executions.objects.get(
                            task_type=task_type, task_id=task_id, completed_at__isnull=True
                        )
                        active_execution_ids.add(execution.id)
                    except Executions.DoesNotExist:
                        pass

    # Find running/queued executions without active Celery tasks
    orphaned_executions = Executions.objects.filter(
        Q(status=TaskStatus.RUNNING) | Q(status=TaskStatus.CREATED), completed_at__isnull=True
    ).exclude(id__in=active_execution_ids)

    results: dict[str, Any] = {
        "checked_at": timezone.now().isoformat(),
        "active_celery_tasks": len(active_execution_ids),
        "orphaned_count": 0,
        "synced": [],
        "errors": [],
    }

    for execution in orphaned_executions:
        try:
            # Only mark as failed if it's been running for a while
            # (to avoid race conditions with newly started tasks)
            if execution.started_at and (timezone.now() - execution.started_at) > timedelta(
                minutes=5
            ):
                execution.status = TaskStatus.FAILED
                execution.completed_at = timezone.now()
                execution.error_message = "Execution orphaned - no corresponding Celery task found"
                execution.save(update_fields=["status", "completed_at", "error_message"])

                # Update parent task
                if execution.task_type == "backtest":
                    task = BacktestTasks.objects.get(id=execution.task_id)
                else:
                    task = TradingTasks.objects.get(id=execution.task_id)

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])

                results["orphaned_count"] += 1
                results["synced"].append(
                    {
                        "execution_id": execution.id,
                        "task_type": execution.task_type,
                        "task_id": execution.task_id,
                    }
                )

                logger.warning(
                    f"Synced orphaned execution: {execution.id} "
                    f"(task_type={execution.task_type}, task_id={execution.task_id})"
                )

        except Exception as e:
            error_msg = f"Error syncing execution {execution.id}: {str(e)}"
            logger.exception(error_msg)
            results["errors"].append(error_msg)

    logger.info(
        f"Celery task status sync complete. "
        f"Found and synced {results['orphaned_count']} orphaned executions"
    )

    return results
