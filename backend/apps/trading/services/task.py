"""Task service layer for managing task lifecycle and execution.

This module provides the service layer for task management, including:
- Task submission to Celery
- Task stopping with graceful shutdown
- Task restart and resume operations
"""

from __future__ import annotations

import logging
from logging import Logger
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from celery.result import AsyncResult

    from apps.trading.models import BacktestTasks, TradingTasks

logger: Logger = logging.getLogger(name=__name__)


def get_celery_result(celery_task_id: str | None) -> AsyncResult | None:
    """Get Celery AsyncResult for a task ID.

    Args:
        celery_task_id: Celery task ID

    Returns:
        AsyncResult | None: Celery AsyncResult if task ID exists, None otherwise
    """
    if celery_task_id:
        from celery.result import AsyncResult

        return AsyncResult(celery_task_id)
    return None


class TaskService:
    """Service for managing task lifecycle.

    This service provides:
    - Task starting with STARTING state
    - Task stopping with STOPPING state
    - Task restart and resume operations
    """

    def start_task(
        self,
        task: BacktestTasks | TradingTasks,
    ) -> BacktestTasks | TradingTasks:
        """Submit a task to Celery for execution.

        Sets task status to STARTING and submits to Celery queue.
        The Celery task will update to RUNNING when it actually starts.

        Args:
            task: Task instance to submit

        Returns:
            BacktestTasks | TradingTasks: The updated task instance

        Raises:
            ValueError: If task is not in CREATED status
            RuntimeError: If Celery submission fails
        """
        from uuid import uuid4

        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks
        from apps.trading.tasks import run_backtest_task, run_trading_task

        logger.info(
            "Submitting task",
            extra={"task_id": task.pk, "task_status": task.status},
        )

        try:
            # Validate task status
            if task.status != TaskStatus.CREATED:
                logger.warning(
                    "Task not in CREATED status",
                    extra={"task_id": task.pk, "current_status": task.status},
                )
                raise ValueError(
                    f"Task must be in CREATED status to submit (current status: {task.status})"
                )

            # Validate task configuration
            is_valid, error_message = task.validate_configuration()
            if not is_valid:
                logger.error(
                    "Task configuration validation failed",
                    extra={"task_id": task.pk, "error": error_message},
                )
                raise ValueError(f"Task configuration is invalid: {error_message}")

            # Determine which Celery task to call based on task type
            if isinstance(task, BacktestTasks):
                celery_task = run_backtest_task
            else:
                celery_task = run_trading_task

            # Generate a unique Celery task ID
            celery_task_id = str(uuid4())

            try:
                # Submit to Celery
                result = celery_task.apply_async(
                    args=[task.pk],
                    task_id=celery_task_id,
                )

                # Update task with Celery task ID and status to STARTING
                # The Celery task will update to RUNNING when it actually starts
                task.celery_task_id = result.id
                task.status = TaskStatus.STARTING
                task.save(update_fields=["celery_task_id", "status", "updated_at"])

                logger.info(
                    "Task submitted successfully",
                    extra={
                        "task_id": task.pk,
                        "celery_task_id": result.id,
                    },
                )

                return task

            except Exception as e:
                logger.error(
                    "Celery submission failed",
                    extra={"task_id": task.pk, "celery_task_id": celery_task_id},
                    exc_info=True,
                )
                raise RuntimeError(f"Failed to submit task to Celery: {str(e)}") from e

        except (ValueError, RuntimeError):
            # Re-raise expected exceptions as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error submitting task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            raise RuntimeError(f"Unexpected error during task submission: {str(e)}") from e

    def stop_task(self, task_id: UUID, mode: str = "graceful") -> bool:
        """Stop a running task.

        Sets task status to STOPPING and triggers the Celery stop task.
        The Celery task will update to STOPPED when it actually stops.

        Args:
            task_id: UUID of the task to stop
            mode: Stop mode ('immediate', 'graceful', 'graceful_close')

        Returns:
            bool: True if stop was successfully initiated, False otherwise

        Raises:
            ValueError: If task does not exist or is not in a stoppable state
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingTasks
        from apps.trading.tasks import stop_backtest_task, stop_trading_task

        logger.info("Stopping task", extra={"task_id": str(task_id), "mode": mode})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            is_backtest = False
            try:
                task = BacktestTasks.objects.get(pk=task_id)
                is_backtest = True
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Validate task is in a stoppable state
            if task.status not in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.PAUSED]:
                logger.warning(
                    "Task not in stoppable state",
                    extra={"task_id": str(task_id), "status": task.status},
                )
                raise ValueError(
                    f"Task cannot be stopped in {task.status} state. "
                    f"Only STARTING, RUNNING, or PAUSED tasks can be stopped."
                )

            # Update task status to STOPPING
            task.status = TaskStatus.STOPPING
            task.save(update_fields=["status", "updated_at"])

            # Trigger the appropriate Celery stop task
            if is_backtest:
                stop_backtest_task.delay(task_id)
            else:
                stop_trading_task.delay(task_id, mode)

            logger.info(
                "Task stop initiated successfully",
                extra={"task_id": str(task_id), "mode": mode},
            )

            return True

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error stopping task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to stop task: {str(e)}") from e

    def pause_task(self, task_id: UUID) -> bool:
        """Pause a running task.

        Sets task status to PAUSED. The task can be resumed later.

        Args:
            task_id: UUID of the task to pause

        Returns:
            bool: True if task was successfully paused, False otherwise

        Raises:
            ValueError: If task does not exist or is not running
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Pausing task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Validate task is running
            if task.status != TaskStatus.RUNNING:
                logger.warning(
                    "Task not in RUNNING state",
                    extra={"task_id": str(task_id), "status": task.status},
                )
                raise ValueError(
                    f"Task cannot be paused in {task.status} state. "
                    "Only RUNNING tasks can be paused."
                )

            # Update task status to PAUSED
            task.status = TaskStatus.PAUSED
            task.save(update_fields=["status", "updated_at"])

            logger.info(
                "Task paused successfully",
                extra={"task_id": str(task_id)},
            )
            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error pausing task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to pause task: {str(e)}") from e

    def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a running task immediately.

        Revokes the Celery task and updates status to STOPPED.
        This is different from stop_task which uses graceful shutdown.

        Args:
            task_id: UUID of the task to cancel

        Returns:
            bool: True if task was successfully cancelled, False otherwise

        Raises:
            ValueError: If task does not exist
        """
        from django.utils import timezone

        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Cancelling task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Only cancel if task is in an active state
            if task.status not in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.PAUSED]:
                logger.warning(
                    "Task not in cancellable state",
                    extra={"task_id": str(task_id), "status": task.status},
                )
                return False

            # Revoke Celery task if it exists
            result = get_celery_result(task.celery_task_id)
            if result:
                result.revoke(terminate=True)

            # Update task status
            task.status = TaskStatus.STOPPED
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at", "updated_at"])

            logger.info(
                "Task cancelled successfully",
                extra={"task_id": str(task_id)},
            )
            return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error cancelling task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to cancel task: {str(e)}") from e

    def restart_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Restart a task from the beginning, clearing all execution data.

        Clears all previous execution data and resets status to CREATED.
        Increments retry_count, then resubmits the task.

        Args:
            task_id: UUID of the task to restart

        Returns:
            BacktestTasks | TradingTasks: The restarted task instance

        Raises:
            ValueError: If task cannot be restarted (e.g., currently running)
            ValueError: If retry_count exceeds max_retries
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingEvents, TradingTasks

        logger.info("Restarting task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            task_type = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
                task_type = "backtest"
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                    task_type = "trading"
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Validate task is not currently running
            if task.status in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]:
                raise ValueError(f"Cannot restart a task in {task.status} state. Stop it first.")

            # Check retry count limit
            if task.retry_count >= task.max_retries:
                logger.warning(
                    "Task retry limit exceeded",
                    extra={
                        "task_id": str(task_id),
                        "retry_count": task.retry_count,
                        "max_retries": task.max_retries,
                    },
                )
                raise ValueError(
                    f"Task has reached maximum retry limit "
                    f"(retry_count={task.retry_count}, max_retries={task.max_retries})"
                )

            # Only restart if task is in a terminal state
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                raise ValueError(
                    f"Task cannot be restarted from {task.status} state. "
                    "Only COMPLETED, FAILED, or STOPPED tasks can be restarted."
                )

            # Clear all events associated with this task
            TradingEvents.objects.filter(task_type=task_type, task_id=task.pk).delete()

            # Clear all execution data
            task.celery_task_id = None
            task.status = TaskStatus.CREATED
            task.started_at = None
            task.completed_at = None
            task.error_message = None
            task.error_traceback = None
            task.retry_count += 1
            task.save()

            logger.info(
                "Task restarted, resubmitting",
                extra={"task_id": str(task_id), "retry_count": task.retry_count},
            )

            # Resubmit the task
            return self.start_task(task)

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error restarting task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to restart task: {str(e)}") from e

    def resume_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Resume a paused task, preserving execution context.

        Preserves existing execution data (started_at, logs, metrics) but clears
        celery_task_id. Resets status to CREATED, then resubmits.

        Args:
            task_id: UUID of the task to resume

        Returns:
            BacktestTasks | TradingTasks: The resumed task instance

        Raises:
            ValueError: If task cannot be resumed (e.g., not paused)
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Resuming task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Validate task is paused
            if task.status != TaskStatus.PAUSED:
                raise ValueError(
                    f"Task cannot be resumed from {task.status} state. "
                    "Only PAUSED tasks can be resumed."
                )

            # Keep existing execution data, just clear celery_task_id and reset status
            task.celery_task_id = None
            task.status = TaskStatus.CREATED
            task.save(update_fields=["celery_task_id", "status", "updated_at"])

            logger.info(
                "Task resumed, resubmitting",
                extra={"task_id": str(task_id)},
            )

            # Resubmit the task
            return self.start_task(task)

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error resuming task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to resume task: {str(e)}") from e
