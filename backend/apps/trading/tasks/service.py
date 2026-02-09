"""Task service layer for managing task lifecycle and execution.

This module provides the service layer for task management, including:
- Task submission to Celery
- Task stopping with graceful shutdown
- Task restart and resume operations
"""

from __future__ import annotations

import logging
from logging import Logger
from uuid import UUID, uuid4

from celery.result import AsyncResult
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, TradingEvent, TradingTask
from apps.trading.tasks import (
    run_backtest_task,
    run_trading_task,
    stop_backtest_task,
    stop_trading_task,
)

logger: Logger = logging.getLogger(name=__name__)


class TaskService:
    """Service for managing task lifecycle.

    This service provides:
    - Task starting with STARTING state
    - Task stopping with STOPPING state
    - Task restart and resume operations
    """

    @staticmethod
    def get_celery_result(celery_task_id: str | None) -> AsyncResult | None:
        """Get Celery AsyncResult for a task ID.

        Args:
            celery_task_id: Celery task ID

        Returns:
            AsyncResult | None: Celery AsyncResult if task ID exists, None otherwise
        """
        if celery_task_id:
            return AsyncResult(celery_task_id)
        return None

    def start_task(self, task: BacktestTask | TradingTask) -> BacktestTask | TradingTask:
        """Submit a task to Celery for execution.

        Sets task status to STARTING and submits to Celery queue.
        The Celery task will update to RUNNING when it actually starts.

        Args:
            task: Task instance to submit

        Returns:
            BacktestTask | TradingTask: The updated task instance

        Raises:
            ValueError: If task is not in CREATED status
            RuntimeError: If Celery submission fails
        """

        logger.info(
            f"[SERVICE:START] Submitting task - task_id={task.pk}, task_status={task.status}, "
            f"instrument={task.instrument}, start_time={getattr(task, 'start_time', 'N/A')}, "
            f"end_time={getattr(task, 'end_time', 'N/A')}"
        )

        try:
            # Validate task status
            if task.status != TaskStatus.CREATED:
                logger.warning(
                    f"[SERVICE:START] INVALID_STATUS - task_id={task.pk}, "
                    f"current_status={task.status}, expected=CREATED"
                )
                raise ValueError(
                    f"Task must be in CREATED status to submit (current status: {task.status})"
                )

            # Validate task configuration
            logger.info(f"[SERVICE:START] Validating configuration - task_id={task.pk}")
            is_valid, error_message = task.validate_configuration()
            if not is_valid:
                logger.error(
                    f"[SERVICE:START] CONFIG_INVALID - task_id={task.pk}, error={error_message}"
                )
                raise ValueError(f"Task configuration is invalid: {error_message}")

            # Determine which Celery task to call based on task type
            if isinstance(task, BacktestTask):
                celery_task = run_backtest_task
                task_type = "backtest"
            else:
                celery_task = run_trading_task
                task_type = "trading"

            logger.info(
                f"[SERVICE:START] Task type determined - task_id={task.pk}, type={task_type}"
            )

            # Generate a unique Celery task ID
            celery_task_id = str(uuid4())
            logger.info(
                f"[SERVICE:START] Generated Celery task ID - task_id={task.pk}, "
                f"celery_task_id={celery_task_id}"
            )

            try:
                # Submit to Celery
                logger.info(
                    f"[SERVICE:START] Submitting to Celery - task_id={task.pk}, "
                    f"celery_task_id={celery_task_id}"
                )
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
                    f"[SERVICE:START] Task submitted to Celery - task_id={task.pk}, "
                    f"celery_task_id={result.id}, new_status={task.status}"
                )

                # Check if worker is responsive
                from celery import current_app

                inspect = current_app.control.inspect()
                active_workers = inspect.active()

                if not active_workers:
                    logger.warning(
                        f"[SERVICE:START] NO_WORKERS - No active Celery workers detected. "
                        f"Task may not be processed. task_id={task.pk}, celery_task_id={result.id}"
                    )
                else:
                    logger.info(
                        f"[SERVICE:START] Active workers found - task_id={task.pk}, "
                        f"workers={list(active_workers.keys())}"
                    )

                return task

            except Exception as e:
                logger.error(
                    f"[SERVICE:START] CELERY_SUBMISSION_FAILED - task_id={task.pk}, "
                    f"celery_task_id={celery_task_id}, error={str(e)}",
                    exc_info=True,
                )
                raise RuntimeError(f"Failed to submit task to Celery: {str(e)}") from e

        except (ValueError, RuntimeError):
            # Re-raise expected exceptions as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                f"[SERVICE:START] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
            raise RuntimeError(f"Unexpected error during task submission: {str(e)}") from e

    def stop_task(self, task_id: UUID, mode: str = "graceful") -> bool:
        """Stop a running task.

        Sets task status to STOPPING and signals Redis coordinator to stop.
        The Celery task will update to STOPPED when it actually stops.

        Args:
            task_id: UUID of the task to stop
            mode: Stop mode ('immediate', 'graceful', 'graceful_close')

        Returns:
            bool: True if stop was successfully initiated, False otherwise

        Raises:
            ValueError: If task does not exist
        """

        logger.info(f"[SERVICE:STOP] Stopping task - task_id={task_id}, mode={mode}")

        try:
            # Try to find the task in either BacktestTask or TradingTask
            task = None
            is_backtest = False
            task_name = None
            try:
                task = BacktestTask.objects.get(pk=task_id)
                is_backtest = True
                task_name = "trading.tasks.run_backtest_task"
                logger.info(f"[SERVICE:STOP] Found backtest task - task_id={task_id}")
            except BacktestTask.DoesNotExist:
                try:
                    task = TradingTask.objects.get(pk=task_id)
                    task_name = "trading.tasks.run_trading_task"
                    logger.info(f"[SERVICE:STOP] Found trading task - task_id={task_id}")
                except TradingTask.DoesNotExist as e:
                    logger.error(f"[SERVICE:STOP] TASK_NOT_FOUND - task_id={task_id}")
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            logger.info(
                f"[SERVICE:STOP] Current task state - task_id={task_id}, status={task.status}, "
                f"celery_task_id={task.celery_task_id}"
            )

            # Allow stopping from ANY state - user control is paramount
            # If already stopped/completed/failed, just return success
            if task.status in [TaskStatus.STOPPED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                logger.info(
                    f"[SERVICE:STOP] Task already in terminal state - task_id={task_id}, "
                    f"status={task.status}"
                )
                return True

            # Update task status to STOPPING in database
            logger.info(f"[SERVICE:STOP] Updating task status to STOPPING - task_id={task_id}")
            task.status = TaskStatus.STOPPING
            task.save(update_fields=["status", "updated_at"])

            # Signal Redis to stop
            logger.info(f"[SERVICE:STOP] Signaling Redis coordinator - task_id={task_id}")
            import redis
            from django.conf import settings

            try:
                redis_client = redis.Redis.from_url(
                    settings.MARKET_REDIS_URL, decode_responses=True
                )
                redis_key = f"task:coord:{task_name}:{task_id}"
                redis_client.hset(redis_key, "status", "stopping")
                redis_client.expire(redis_key, 3600)
                logger.info(
                    f"[SERVICE:STOP] Redis signal sent - task_id={task_id}, key={redis_key}"
                )
                redis_client.close()
            except Exception as e:
                logger.warning(
                    f"[SERVICE:STOP] Redis signal failed (non-fatal) - task_id={task_id}, error={str(e)}"
                )

            # Revoke Celery task if it exists
            if task.celery_task_id:
                try:
                    logger.info(
                        f"[SERVICE:STOP] Revoking Celery task - task_id={task_id}, "
                        f"celery_task_id={task.celery_task_id}"
                    )
                    from celery import current_app

                    current_app.control.revoke(
                        task.celery_task_id, terminate=True, signal="SIGKILL"
                    )
                    logger.info(f"[SERVICE:STOP] Celery task revoked - task_id={task_id}")
                except Exception as e:
                    logger.warning(
                        f"[SERVICE:STOP] Celery revoke failed (non-fatal) - task_id={task_id}, "
                        f"error={str(e)}"
                    )

            # Trigger the appropriate Celery stop task
            logger.info(f"[SERVICE:STOP] Triggering Celery stop task - task_id={task_id}")
            try:
                if is_backtest:
                    stop_backtest_task.delay(task_id)
                else:
                    stop_trading_task.delay(task_id, mode)
            except Exception as e:
                logger.warning(
                    f"[SERVICE:STOP] Stop task trigger failed (non-fatal) - task_id={task_id}, "
                    f"error={str(e)}"
                )

            logger.info(f"[SERVICE:STOP] SUCCESS - Stop initiated for task_id={task_id}")

            return True
        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                f"[SERVICE:STOP] UNEXPECTED_ERROR - task_id={task_id}, error={str(e)}",
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

        logger.info("Pausing task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTask or TradingTask
            task = None
            try:
                task = BacktestTask.objects.get(pk=task_id)
            except BacktestTask.DoesNotExist:
                try:
                    task = TradingTask.objects.get(pk=task_id)
                except TradingTask.DoesNotExist as e:
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

        logger.info("Cancelling task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTask or TradingTask
            task = None
            try:
                task = BacktestTask.objects.get(pk=task_id)
            except BacktestTask.DoesNotExist:
                try:
                    task = TradingTask.objects.get(pk=task_id)
                except TradingTask.DoesNotExist as e:
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
            result = self.get_celery_result(task.celery_task_id)
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
    ) -> BacktestTask | TradingTask:
        """Restart a task from the beginning, clearing all execution data.

        Clears all previous execution data and resets status to CREATED.
        Then resubmits the task.

        Args:
            task_id: UUID of the task to restart

        Returns:
            BacktestTask | TradingTask: The restarted task instance

        Raises:
            ValueError: If task does not exist
        """

        logger.info(f"[SERVICE:RESTART] Restarting task - task_id={task_id}")

        try:
            # Try to find the task in either BacktestTask or TradingTask
            task = None
            task_type = None
            try:
                task = BacktestTask.objects.get(pk=task_id)
                task_type = "backtest"
                logger.info(f"[SERVICE:RESTART] Found backtest task - task_id={task_id}")
            except BacktestTask.DoesNotExist:
                try:
                    task = TradingTask.objects.get(pk=task_id)
                    task_type = "trading"
                    logger.info(f"[SERVICE:RESTART] Found trading task - task_id={task_id}")
                except TradingTask.DoesNotExist as e:
                    logger.error(f"[SERVICE:RESTART] TASK_NOT_FOUND - task_id={task_id}")
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            logger.info(
                f"[SERVICE:RESTART] Current task state - task_id={task_id}, status={task.status}, "
                f"celery_task_id={task.celery_task_id}, started_at={task.started_at}, "
                f"completed_at={task.completed_at}"
            )

            # If task is active, stop it first
            if task.status in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]:
                logger.info(
                    f"[SERVICE:RESTART] Task is active, stopping first - task_id={task_id}, "
                    f"status={task.status}"
                )
                try:
                    self.stop_task(task_id)
                    # Wait a moment for stop to take effect
                    import time

                    time.sleep(1)
                    task.refresh_from_db()
                    logger.info(
                        f"[SERVICE:RESTART] Task stopped - task_id={task_id}, new_status={task.status}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[SERVICE:RESTART] Stop failed, forcing restart anyway - task_id={task_id}, "
                        f"error={str(e)}"
                    )

            # Force revoke any Celery task
            if task.celery_task_id:
                try:
                    logger.info(
                        f"[SERVICE:RESTART] Force revoking Celery task - task_id={task_id}, "
                        f"celery_task_id={task.celery_task_id}"
                    )
                    from celery import current_app

                    current_app.control.revoke(
                        task.celery_task_id, terminate=True, signal="SIGKILL"
                    )
                except Exception as e:
                    logger.warning(
                        f"[SERVICE:RESTART] Celery revoke failed (non-fatal) - task_id={task_id}, "
                        f"error={str(e)}"
                    )

            # Clear all events associated with this task
            logger.info(
                f"[SERVICE:RESTART] Clearing events - task_id={task_id}, task_type={task_type}"
            )
            events_deleted = TradingEvent.objects.filter(
                task_type=task_type, task_id=task.pk
            ).delete()
            logger.info(
                f"[SERVICE:RESTART] Events cleared - task_id={task_id}, count={events_deleted[0]}"
            )

            # Clear execution state
            logger.info(f"[SERVICE:RESTART] Clearing execution state - task_id={task_id}")
            from apps.trading.models.state import ExecutionState

            ExecutionState.objects.filter(task_type=task_type, task_id=task.pk).delete()

            # Clear all execution data
            logger.info(f"[SERVICE:RESTART] Clearing execution data - task_id={task_id}")
            task.celery_task_id = None
            task.status = TaskStatus.CREATED
            task.started_at = None
            task.completed_at = None
            task.error_message = None
            task.error_traceback = None
            task.save()

            logger.info(
                f"[SERVICE:RESTART] Task reset to CREATED - task_id={task_id}, "
                f"new_status={task.status}"
            )

            # Resubmit the task
            logger.info(f"[SERVICE:RESTART] Resubmitting task - task_id={task_id}")
            return self.start_task(task)

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"[SERVICE:RESTART] UNEXPECTED_ERROR - task_id={task_id}, error={str(e)}",
                exc_info=True,
            )
            raise ValueError(f"Failed to restart task: {str(e)}") from e

    def resume_task(
        self,
        task_id: UUID,
    ) -> BacktestTask | TradingTask:
        """Resume a paused task, preserving execution context.

        Preserves existing execution data (started_at, logs, metrics) but clears
        celery_task_id. Resets status to CREATED, then resubmits.

        Args:
            task_id: UUID of the task to resume

        Returns:
            BacktestTask | TradingTask: The resumed task instance

        Raises:
            ValueError: If task cannot be resumed (e.g., not paused)
        """

        logger.info("Resuming task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTask or TradingTask
            task = None
            try:
                task = BacktestTask.objects.get(pk=task_id)
            except BacktestTask.DoesNotExist:
                try:
                    task = TradingTask.objects.get(pk=task_id)
                except TradingTask.DoesNotExist as e:
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

            # Check for status mismatch: task is PAUSED in DB but Celery task is still running
            if task.celery_task_id:
                result = self.get_celery_result(task.celery_task_id)
                if result:
                    celery_state = result.state
                    # Check if Celery task is in an active state
                    if celery_state in ["PENDING", "STARTED", "RETRY"]:
                        logger.warning(
                            "Task status mismatch detected",
                            extra={
                                "task_id": str(task_id),
                                "db_status": task.status,
                                "celery_state": celery_state,
                                "celery_task_id": task.celery_task_id,
                            },
                        )
                        raise ValueError(
                            f"Task status mismatch: task is marked as PAUSED in database "
                            f"but Celery task is still {celery_state}. "
                            "Please wait for the task to fully stop before resuming."
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
