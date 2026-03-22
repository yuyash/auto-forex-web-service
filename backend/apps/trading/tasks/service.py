"""Task service layer for managing task lifecycle and execution.

This module provides the service layer for task management, including:
- Task submission to Celery
- Task stopping with graceful shutdown
- Task restart and resume operations
"""

from __future__ import annotations

import logging
from logging import Logger
from typing import cast
from uuid import UUID, uuid4

from celery.result import AsyncResult
from django.db import transaction

from apps.trading.enums import StopMode, TaskStatus
from apps.trading.models import (
    BacktestTask,
    TradingEvent,
    TradingTask,
)
from apps.trading.services.execution_lifecycle import sync_terminal_execution_artifacts
from apps.trading.tasks.lifecycle_writes import TaskLifecycleWriter
from apps.trading.tasks import (
    run_backtest_task,
    run_trading_task,
    stop_backtest_task,
    stop_trading_task,
)

logger: Logger = logging.getLogger(name=__name__)


class TaskServiceError(Exception):
    """Base exception for task service failures."""


class TaskValidationError(TaskServiceError, ValueError):
    """Raised when a task request fails domain validation."""


class TaskConflictError(TaskServiceError, ValueError):
    """Raised when a task conflicts with current system state."""


class TaskSubmissionError(TaskServiceError, RuntimeError):
    """Raised when dispatching a task to workers fails."""


class TaskLookupError(TaskValidationError):
    """Raised when a task cannot be found."""


class TaskService:
    """Service for managing task lifecycle.

    This service provides:
    - Task starting with STARTING state
    - Task stopping with STOPPING state
    - Task restart and resume operations
    """

    writer = TaskLifecycleWriter(logger=logger)

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

    @staticmethod
    def _emit_task_lifecycle_event(
        *,
        task: BacktestTask | TradingTask,
        task_type: str | None = None,
        kind: str,
        description: str,
        extra_details: dict[str, object] | None = None,
    ) -> None:
        resolved_task_type = task_type or TaskService._resolve_task_type(task)
        details = {
            "kind": kind,
            "status": str(task.status),
            "task_name": str(getattr(task, "name", "")),
        }
        if extra_details:
            details.update(extra_details)

        try:
            TradingEvent.objects.create(
                event_type="status_changed",
                severity="info",
                description=description,
                user=getattr(task, "user", None),
                account=getattr(task, "oanda_account", None),
                instrument=getattr(task, "instrument", None),
                task_type=resolved_task_type,
                task_id=task.pk,
                execution_id=getattr(task, "execution_id", None),
                details=details,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning(
                "[SERVICE:EVENT] Failed to persist lifecycle event - task_id=%s, kind=%s, error=%s",
                task.pk,
                kind,
                exc,
            )

    @staticmethod
    def _resolve_task_type(task: BacktestTask | TradingTask) -> str:
        model_name = str(getattr(getattr(task, "_meta", None), "model_name", "")).lower()
        if model_name == "backtesttask":
            return "backtest"
        if model_name == "tradingtask":
            return "trading"

        class_name = str(task.__class__.__name__).lower()
        if class_name.startswith("backtest"):
            return "backtest"
        if class_name.startswith("trading"):
            return "trading"

        if hasattr(task, "start_time") and hasattr(task, "end_time"):
            return "backtest"

        return "trading"

    @staticmethod
    def _dispatch_task(task: BacktestTask | TradingTask, task_type: str) -> None:
        celery_task = run_backtest_task if task_type == "backtest" else run_trading_task
        celery_task.apply_async(
            args=[task.pk],
            task_id=str(task.execution_id),
        )

    @staticmethod
    def _get_task_and_type(task_id: UUID) -> tuple[BacktestTask | TradingTask, str]:
        try:
            return BacktestTask.objects.get(pk=task_id), "backtest"
        except BacktestTask.DoesNotExist:
            try:
                return TradingTask.objects.get(pk=task_id), "trading"
            except TradingTask.DoesNotExist as exc:
                raise TaskLookupError(f"Task with id {task_id} does not exist") from exc

    @staticmethod
    def _get_task_model(task_type: str):
        return BacktestTask if task_type == "backtest" else TradingTask

    @staticmethod
    def _ensure_task_status(
        task: BacktestTask | TradingTask,
        *,
        allowed: tuple[TaskStatus, ...],
        message: str,
    ) -> None:
        if task.status not in allowed:
            raise TaskValidationError(message)

    @staticmethod
    def _ensure_trading_account_available(task: TradingTask) -> None:
        active_statuses = [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]
        active_task = (
            TradingTask.objects.filter(
                oanda_account=task.oanda_account,
                status__in=active_statuses,
            )
            .exclude(pk=task.pk)
            .first()
        )
        if active_task:
            raise TaskConflictError(
                f"Account already has an active task: '{active_task.name}' "
                f"(status: {active_task.status}). "
                f"Please stop the existing task before starting a new one."
            )

    def _prepare_locked_start_task(
        self,
        task: BacktestTask | TradingTask,
        *,
        model_class,
    ) -> BacktestTask | TradingTask:
        with transaction.atomic():
            locked_task = model_class.objects.select_for_update().get(pk=task.pk)
            self._ensure_task_status(
                locked_task,
                allowed=(TaskStatus.CREATED,),
                message=(
                    "Task must be in CREATED status to submit "
                    f"(current status: {locked_task.status})"
                ),
            )
            if isinstance(locked_task, TradingTask):
                self._ensure_trading_account_available(locked_task)

            is_valid, error_message = locked_task.validate_configuration()
            if not is_valid:
                raise TaskValidationError(f"Task configuration is invalid: {error_message}")

            locked_task.execution_id = uuid4()
            locked_task.status = TaskStatus.STARTING
            locked_task.save(update_fields=["execution_id", "status", "updated_at"])
            return locked_task

    def _prepare_detached_start_task(
        self, task: BacktestTask | TradingTask
    ) -> BacktestTask | TradingTask:
        self._ensure_task_status(
            task,
            allowed=(TaskStatus.CREATED,),
            message=f"Task must be in CREATED status to submit (current status: {task.status})",
        )
        if isinstance(task, TradingTask):
            self._ensure_trading_account_available(task)

        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            raise TaskValidationError(f"Task configuration is invalid: {error_message}")

        task.execution_id = uuid4()
        task.status = TaskStatus.STARTING
        try:
            task.save(update_fields=["execution_id", "status", "updated_at"])
        except TypeError:
            task.save()
        return task

    def _finalize_terminal_task(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
        status: TaskStatus,
        description: str,
        kind: str,
        extra_updates: dict[str, object] | None = None,
    ) -> None:
        self.writer.finalize_terminal_task(
            task=task,
            task_type=task_type,
            status=status,
            extra_updates=extra_updates,
            sync_artifacts=sync_terminal_execution_artifacts,
        )
        self._emit_task_lifecycle_event(
            task=task,
            task_type=task_type,
            kind=kind,
            description=description,
        )

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

        is_backtest_task = isinstance(task, BacktestTask) or hasattr(task, "start_time")
        model_class = BacktestTask if is_backtest_task else TradingTask

        try:
            if type(task) in (BacktestTask, TradingTask):
                task = self._prepare_locked_start_task(task, model_class=model_class)
            else:
                task = self._prepare_detached_start_task(task)

            task_type = "backtest" if is_backtest_task else "trading"

            logger.info(
                "[SERVICE:START] Task type determined - task_id=%s, type=%s, execution_id=%s",
                task.pk,
                task_type,
                task.execution_id,
            )
            logger.info(
                "[SERVICE:START] Submitting to Celery - task_id=%s, execution_id=%s",
                task.pk,
                task.execution_id,
            )
            self._dispatch_task(task, task_type)

            logger.info(
                "[SERVICE:START] Task submitted to Celery - task_id=%s, execution_id=%s, new_status=%s",
                task.pk,
                task.execution_id,
                task.status,
            )
            self._emit_task_lifecycle_event(
                task=task,
                task_type=task_type,
                kind="task_start_requested",
                description="Task start requested",
            )

            from celery import current_app

            inspect = current_app.control.inspect(timeout=3.0)
            active_workers = inspect.active()

            if not active_workers:
                logger.warning(
                    "[SERVICE:START] NO_WORKERS - No active Celery workers detected. task_id=%s, execution_id=%s",
                    task.pk,
                    task.execution_id,
                )
            else:
                logger.info(
                    "[SERVICE:START] Active workers found - task_id=%s, workers=%s",
                    task.pk,
                    list(active_workers.keys()),
                )

            return task

        except TaskServiceError:
            raise
        except Exception as e:
            logger.error(
                "[SERVICE:START] CELERY_SUBMISSION_FAILED - task_id=%s, execution_id=%s, error=%s",
                task.pk,
                getattr(task, "execution_id", None),
                str(e),
                exc_info=True,
            )
            if type(task) in (BacktestTask, TradingTask):
                model_class.objects.filter(pk=task.pk).update(
                    status=TaskStatus.CREATED,
                    execution_id=None,
                )
                task.refresh_from_db()
            else:
                task.status = TaskStatus.CREATED
                task.execution_id = None
                try:
                    task.save(update_fields=["status", "execution_id"])
                except TypeError:
                    task.save()
            raise TaskSubmissionError(f"Failed to submit task to Celery: {str(e)}") from e

    def recover_trading_task(self, task: TradingTask) -> TradingTask:
        """Requeue an orphaned trading task in the same execution run."""

        previous_status = task.status
        previous_execution_id = task.execution_id

        with transaction.atomic():
            locked_task = TradingTask.objects.select_for_update().get(pk=task.pk)

            if locked_task.status not in (TaskStatus.STARTING, TaskStatus.RUNNING):
                raise ValueError(
                    "Orphan recovery requires task in STARTING/RUNNING state; "
                    f"got {locked_task.status}"
                )
            if not locked_task.execution_id:
                raise ValueError("Cannot recover trading task without an execution_id")

            locked_task.status = TaskStatus.STARTING
            locked_task.completed_at = None
            locked_task.error_message = None
            locked_task.error_traceback = None
            locked_task.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "error_traceback",
                    "updated_at",
                ]
            )
            task = locked_task

        try:
            self._dispatch_task(task, "trading")
            return task
        except Exception as exc:
            TradingTask.objects.filter(pk=task.pk).update(
                status=TaskStatus.FAILED,
                error_message=f"Failed to requeue orphaned trading task: {exc}",
            )
            task.refresh_from_db()
            raise RuntimeError(
                "Failed to requeue orphaned trading task "
                f"(prev_status={previous_status}, prev_execution_id={previous_execution_id})"
            ) from exc

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
            try:
                stop_mode = StopMode(mode)
            except ValueError as e:
                raise ValueError(f"Invalid stop mode: {mode}") from e

            task, task_type = self._get_task_and_type(task_id)
            is_backtest = task_type == "backtest"
            task_name = (
                "trading.tasks.run_backtest_task"
                if is_backtest
                else "trading.tasks.run_trading_task"
            )

            logger.info(
                f"[SERVICE:STOP] Current task state - task_id={task_id}, status={task.status}, "
                f"execution_id={task.execution_id}"
            )

            # Allow stopping from ANY state - user control is paramount
            # If already stopped/completed/failed, just return success
            if task.status in [TaskStatus.STOPPED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                logger.info(
                    f"[SERVICE:STOP] Already in terminal state: {task.status} - task_id={task_id}"
                )
                return True

            # Update task status to STOPPING in database
            logger.info(
                f"[SERVICE:STOP] Transitioning: {task.status} -> STOPPING - task_id={task_id}, "
                f"task_type={task_type}"
            )
            task.status = TaskStatus.STOPPING
            update_fields = ["status", "updated_at"]
            if not is_backtest and stop_mode == StopMode.GRACEFUL_CLOSE:
                trading_task = cast(TradingTask, task)
                trading_task.sell_on_stop = True
                update_fields.append("sell_on_stop")
            task.save(update_fields=update_fields)
            logger.info(
                f"[SERVICE:STOP] Current: STOPPING - task_id={task_id}, task_type={task_type}"
            )

            # Signal Redis to stop
            logger.info(f"[SERVICE:STOP] Signaling Redis coordinator - task_id={task_id}")
            import redis
            from django.conf import settings

            try:
                redis_client = redis.Redis.from_url(
                    settings.MARKET_REDIS_URL, decode_responses=True
                )
                redis_instance_key = f"{task_id}:{task.execution_id}"
                redis_key = f"task:coord:{task_name}:{redis_instance_key}"
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

            # IMMEDIATE mode force-revokes running Celery task.
            if stop_mode == StopMode.IMMEDIATE and task.execution_id:
                try:
                    logger.info(
                        f"[SERVICE:STOP] Immediate revoke Celery task - task_id={task_id}, "
                        f"execution_id={task.execution_id}"
                    )
                    from celery import current_app

                    current_app.control.revoke(
                        str(task.execution_id), terminate=True, signal="SIGKILL"
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
                    stop_trading_task.delay(task_id, stop_mode.value)
            except Exception as e:
                logger.warning(
                    f"[SERVICE:STOP] Stop task trigger failed (non-fatal) - task_id={task_id}, "
                    f"error={str(e)}"
                )

            logger.info(f"[SERVICE:STOP] SUCCESS - Stop initiated for task_id={task_id}")
            self._emit_task_lifecycle_event(
                task=task,
                task_type=task_type,
                kind="task_stop_requested",
                description="Task stop requested",
                extra_details={"mode": stop_mode.value},
            )

            return True
        except TaskValidationError:
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
            task, task_type = self._get_task_and_type(task_id)

            self._ensure_task_status(
                task,
                allowed=(TaskStatus.RUNNING,),
                message=(
                    f"Task cannot be paused in {task.status} state. "
                    "Only RUNNING tasks can be paused."
                ),
            )

            # Update task status to PAUSED
            self.writer.persist_state(task, status=TaskStatus.PAUSED)
            self._emit_task_lifecycle_event(
                task=task,
                task_type=task_type,
                kind="task_paused",
                description="Task paused",
            )

            logger.info(
                "Task paused successfully",
                extra={"task_id": str(task_id)},
            )
            return True

        except TaskValidationError:
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
            task, task_type = self._get_task_and_type(task_id)

            # Only cancel if task is in an active state
            if task.status not in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.PAUSED]:
                logger.warning(
                    "Task not in cancellable state",
                    extra={"task_id": str(task_id), "status": task.status},
                )
                return False

            # Revoke Celery task if it exists
            result = self.get_celery_result(str(task.execution_id) if task.execution_id else None)
            if result:
                result.revoke(terminate=True)

            self._finalize_terminal_task(
                task=task,
                task_type=task_type,
                status=TaskStatus.STOPPED,
                description="Task cancelled",
                kind="task_cancelled",
            )

            logger.info(
                "Task cancelled successfully",
                extra={"task_id": str(task_id)},
            )
            return True

        except TaskValidationError:
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
            task, task_type = self._get_task_and_type(task_id)
            logger.info(f"[SERVICE:RESTART] Found {task_type} task - task_id={task_id}")

            logger.info(
                f"[SERVICE:RESTART] Current task state - task_id={task_id}, status={task.status}, "
                f"execution_id={task.execution_id}, started_at={task.started_at}, "
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
            if task.execution_id:
                try:
                    logger.info(
                        f"[SERVICE:RESTART] Force revoking Celery task - task_id={task_id}, "
                        f"execution_id={task.execution_id}"
                    )
                    from celery import current_app

                    current_app.control.revoke(
                        str(task.execution_id), terminate=True, signal="SIGKILL"
                    )
                except Exception as e:
                    logger.warning(
                        f"[SERVICE:RESTART] Celery revoke failed (non-fatal) - task_id={task_id}, "
                        f"error={str(e)}"
                    )

            logger.info(
                f"[SERVICE:RESTART] Clearing execution history - task_id={task_id}, task_type={task_type}"
            )
            self.writer.clear_execution_history(task=task, task_type=task_type)

            # Clear all execution data using QuerySet.update() for an atomic,
            # single-statement reset.  This avoids the race where a full-model
            # save() might silently fail to commit before the Celery worker
            # reads the row.
            logger.info(f"[SERVICE:RESTART] Clearing execution data - task_id={task_id}")
            model_class = type(task)
            rows = model_class.objects.filter(pk=task.pk).update(
                execution_id=None,
                status=TaskStatus.CREATED,
                started_at=None,
                completed_at=None,
                error_message=None,
                error_traceback=None,
            )
            logger.info(
                f"[SERVICE:RESTART] DB update result - task_id={task_id}, rows_updated={rows}"
            )

            # Reload the object so the in-memory state matches the DB
            task.refresh_from_db()

            logger.info(
                f"[SERVICE:RESTART] Task reset to CREATED - task_id={task_id}, "
                f"new_status={task.status}"
            )

            if task.status != TaskStatus.CREATED:
                raise RuntimeError(
                    f"Failed to reset task status: expected CREATED, got {task.status}"
                )
            self._emit_task_lifecycle_event(
                task=task,
                task_type=task_type,
                kind="task_restart_requested",
                description="Task restart requested",
            )

            # Resubmit the task
            logger.info(f"[SERVICE:RESTART] Resubmitting task - task_id={task_id}")
            return self.start_task(task)

        except TaskValidationError:
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

        Preserves existing execution data (started_at, logs, metrics) and
        resubmits the same execution run so persisted state can be loaded.

        Args:
            task_id: UUID of the task to resume

        Returns:
            BacktestTask | TradingTask: The resumed task instance

        Raises:
            ValueError: If task cannot be resumed (e.g., not paused)
        """

        logger.info("Resuming task", extra={"task_id": str(task_id)})

        try:
            task, task_type = self._get_task_and_type(task_id)

            model_class = self._get_task_model(task_type)

            with transaction.atomic():
                locked_task = model_class.objects.select_for_update().get(pk=task.pk)

                if locked_task.status != TaskStatus.PAUSED:
                    raise TaskValidationError(
                        f"Task cannot be resumed from {locked_task.status} state. "
                        "Only PAUSED tasks can be resumed."
                    )

                if not locked_task.execution_id:
                    raise TaskValidationError("Cannot resume task without an execution_id")

                result = self.get_celery_result(str(locked_task.execution_id))
                if result:
                    celery_state = result.state
                    if celery_state in ["PENDING", "STARTED", "RETRY"]:
                        logger.warning(
                            "Task status mismatch detected",
                            extra={
                                "task_id": str(task_id),
                                "db_status": locked_task.status,
                                "celery_state": celery_state,
                                "execution_id": str(locked_task.execution_id),
                            },
                        )
                        raise TaskValidationError(
                            f"Task status mismatch: task is marked as PAUSED in database "
                            f"but Celery task is still {celery_state}. "
                            "Please wait for the task to fully stop before resuming."
                        )

                locked_task.status = TaskStatus.STARTING
                locked_task.save(update_fields=["status", "updated_at"])
                task = locked_task
            self._emit_task_lifecycle_event(
                task=task,
                task_type=task_type,
                kind="task_resume_requested",
                description="Task resume requested",
            )

            logger.info(
                "Task resumed, resubmitting",
                extra={"task_id": str(task_id)},
            )

            self._dispatch_task(task, task_type)
            return task

        except TaskValidationError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error resuming task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to resume task: {str(e)}") from e
