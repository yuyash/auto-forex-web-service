"""
Monitoring tasks for task status reconciliation.

This module provides periodic tasks that monitor task health and
automatically reconcile task statuses with Celery task states.
"""

from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTasks, TradingTasks

logger: Logger = getLogger(__name__)


@shared_task(name="trading.reconcile_task_statuses")
def reconcile_task_statuses() -> object:
    """
    Reconcile task statuses with Celery task states.

    This periodic task queries all running tasks and compares their status
    with the corresponding Celery task state. If a mismatch is detected,
    the task status is updated to match the Celery state.

    This helps recover from situations where:
    - Celery tasks complete but fail to update the task status
    - Network issues prevent status updates
    - Application crashes during status transitions

    Returns:
        Dictionary with reconciliation results including:
        - checked_at: Timestamp when reconciliation ran
        - backtest_checked: Number of backtest tasks checked
        - trading_checked: Number of trading tasks checked
        - backtest_reconciled: Number of backtest tasks reconciled
        - trading_reconciled: Number of trading tasks reconciled
        - reconciled_tasks: List of reconciled task details
        - errors: List of any errors encountered
    """
    checked_at = timezone.now()
    reconciled_tasks: list[dict[str, Any]] = []
    errors: list[str] = []

    backtest_checked = 0
    trading_checked = 0
    backtest_reconciled = 0
    trading_reconciled = 0

    logger.info("Starting task status reconciliation")

    # Reconcile BacktestTasks
    try:
        running_backtest_tasks = BacktestTasks.objects.filter(status=TaskStatus.RUNNING)
        backtest_checked = running_backtest_tasks.count()

        for task in running_backtest_tasks:
            try:
                result = task.get_celery_result()
                if result:
                    celery_state = result.state
                    expected_status = _map_celery_to_task_status(celery_state)

                    if task.status != expected_status:
                        logger.warning(
                            f"Status mismatch for BacktestTask {task.id} ('{task.name}'): "  # type: ignore[attr-defined]
                            f"Task={task.status}, Celery={celery_state}, Expected={expected_status}"
                        )

                        # Update task status atomically
                        with transaction.atomic():
                            task.status = expected_status
                            if expected_status in [
                                TaskStatus.COMPLETED,
                                TaskStatus.FAILED,
                                TaskStatus.STOPPED,
                            ]:
                                task.completed_at = checked_at
                            task.save(update_fields=["status", "completed_at", "updated_at"])

                        backtest_reconciled += 1
                        reconciled_tasks.append(
                            {
                                "task_id": str(task.id),  # type: ignore[attr-defined]
                                "task_name": task.name,
                                "task_type": "backtest",
                                "old_status": task.status,
                                "new_status": expected_status,
                                "celery_state": celery_state,
                            }
                        )

                        logger.info(
                            f"Reconciled BacktestTask {task.id}: {task.status} -> {expected_status}"  # type: ignore[attr-defined]
                        )
            except Exception as e:
                error_msg = f"Error reconciling BacktestTask {task.id}: {str(e)}"  # type: ignore[attr-defined]
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

    except Exception as e:
        error_msg = f"Error querying backtest tasks: {str(e)}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)

    # Reconcile TradingTasks
    try:
        running_trading_tasks = TradingTasks.objects.filter(status=TaskStatus.RUNNING)
        trading_checked = running_trading_tasks.count()

        for task in running_trading_tasks:
            try:
                result = task.get_celery_result()
                if result:
                    celery_state = result.state
                    expected_status = _map_celery_to_task_status(celery_state)

                    if task.status != expected_status:
                        logger.warning(
                            f"Status mismatch for TradingTask {task.id} ('{task.name}'): "  # type: ignore[attr-defined]
                            f"Task={task.status}, Celery={celery_state}, Expected={expected_status}"
                        )

                        # Update task status atomically
                        with transaction.atomic():
                            task.status = expected_status
                            if expected_status in [
                                TaskStatus.COMPLETED,
                                TaskStatus.FAILED,
                                TaskStatus.STOPPED,
                            ]:
                                task.completed_at = checked_at
                            task.save(update_fields=["status", "completed_at", "updated_at"])

                        trading_reconciled += 1
                        reconciled_tasks.append(
                            {
                                "task_id": str(task.id),  # type: ignore[attr-defined]
                                "task_name": task.name,
                                "task_type": "trading",
                                "old_status": task.status,
                                "new_status": expected_status,
                                "celery_state": celery_state,
                            }
                        )

                        logger.info(
                            f"Reconciled TradingTask {task.id}: {task.status} -> {expected_status}"  # type: ignore[attr-defined]
                        )
            except Exception as e:
                error_msg = f"Error reconciling TradingTask {task.id}: {str(e)}"  # type: ignore[attr-defined]
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

    except Exception as e:
        error_msg = f"Error querying trading tasks: {str(e)}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)

    total_checked = backtest_checked + trading_checked
    total_reconciled = backtest_reconciled + trading_reconciled

    logger.info(
        f"Task status reconciliation completed: "
        f"checked={total_checked}, reconciled={total_reconciled}, errors={len(errors)}"
    )

    return {
        "checked_at": checked_at.isoformat(),
        "backtest_checked": backtest_checked,
        "trading_checked": trading_checked,
        "backtest_reconciled": backtest_reconciled,
        "trading_reconciled": trading_reconciled,
        "total_checked": total_checked,
        "total_reconciled": total_reconciled,
        "reconciled_tasks": reconciled_tasks,
        "errors": errors,
    }


def _map_celery_to_task_status(celery_state: str) -> TaskStatus:
    """
    Map Celery task state to Task status.

    Args:
        celery_state: Celery task state (PENDING, STARTED, SUCCESS, FAILURE, REVOKED)

    Returns:
        TaskStatus: Corresponding task status
    """
    celery_to_task_status = {
        "PENDING": TaskStatus.PENDING,
        "STARTED": TaskStatus.RUNNING,
        "SUCCESS": TaskStatus.COMPLETED,
        "FAILURE": TaskStatus.FAILED,
        "REVOKED": TaskStatus.STOPPED,
    }
    return celery_to_task_status.get(celery_state, TaskStatus.RUNNING)
