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
from django.db import transaction
from django.utils import timezone as _timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import (
    BacktestTask,
    TradingTask,
)
from apps.trading.tasks.lifecycle_commands import TaskLifecycleCommands
from apps.trading.tasks.lifecycle_events import TaskLifecycleEventPublisher
from apps.trading.tasks.lifecycle_writes import TaskLifecycleWriter
from apps.trading.tasks import (
    run_backtest_task,
    run_trading_task,
    stop_backtest_task as _stop_backtest_task,
    stop_trading_task as _stop_trading_task,
)

logger: Logger = logging.getLogger(name=__name__)
timezone = _timezone
stop_backtest_task = _stop_backtest_task
stop_trading_task = _stop_trading_task


class TaskServiceError(Exception):
    """Base exception for task service failures."""


class TaskValidationError(TaskServiceError, ValueError):
    """Raised when a task request fails domain validation."""


class TaskConflictError(TaskServiceError, ValueError):
    """Raised when a task conflicts with current system state."""


class TaskCapacityError(TaskConflictError):
    """Raised when worker capacity is insufficient for a new task."""

    def __init__(
        self,
        message: str,
        *,
        decision: object | None = None,
    ) -> None:
        super().__init__(message)
        self.decision = decision


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

    def __init__(self) -> None:
        from apps.trading.services.task_capacity import TaskCapacityService

        self.writer = TaskLifecycleWriter(logger=logger)
        self.events = TaskLifecycleEventPublisher(logger=logger)
        self.commands = TaskLifecycleCommands(service=self, logger=logger, events=self.events)
        self.capacity = TaskCapacityService()

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
        queue = "backtest" if task_type == "backtest" else "trading"
        celery_task_id = getattr(task, "celery_task_id", None)
        if not celery_task_id:
            # Defensive: should have been set by start/resume/restart, but
            # if it is missing we still need a unique Celery id so the
            # worker can accept the message.
            celery_task_id = uuid4()
            type(task).objects.filter(pk=task.pk).update(celery_task_id=celery_task_id)
            task.celery_task_id = celery_task_id
        celery_task.apply_async(
            args=[task.pk],
            task_id=str(celery_task_id),
            queue=queue,
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
        active_statuses = [
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.STOPPING,
        ]
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
            self._ensure_worker_capacity_available(locked_task)

            is_valid, error_message = locked_task.validate_configuration()
            if not is_valid:
                raise TaskValidationError(f"Task configuration is invalid: {error_message}")

            locked_task.execution_id = uuid4()
            locked_task.celery_task_id = uuid4()
            locked_task.status = TaskStatus.STARTING
            locked_task.save(
                update_fields=["execution_id", "celery_task_id", "status", "updated_at"]
            )
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
        self._ensure_worker_capacity_available(task)

        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            raise TaskValidationError(f"Task configuration is invalid: {error_message}")

        task.execution_id = uuid4()
        task.celery_task_id = uuid4()
        task.status = TaskStatus.STARTING
        try:
            task.save(update_fields=["execution_id", "celery_task_id", "status", "updated_at"])
        except TypeError:
            task.save()
        return task

    def _ensure_worker_capacity_available(self, task: BacktestTask | TradingTask) -> None:
        admission = self.capacity.get_task_admission(task)
        if admission.allowed:
            return
        raise TaskCapacityError(admission.reason, decision=admission)

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
            status=status,
            extra_updates=extra_updates,
        )
        self.events.publish(
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

        try:
            return self.commands.start(task)

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
            # Rotate celery_task_id so the new Celery job is not suppressed
            # by the revoke list left over from the previous (orphaned)
            # worker.  execution_id is preserved so execution-scoped state
            # (ExecutionState, positions, events, ...) stays continuous.
            locked_task.celery_task_id = uuid4()
            locked_task.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "error_traceback",
                    "celery_task_id",
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

    def stop_task(
        self,
        task_id: UUID,
        mode: str = "graceful",
        *,
        drain_duration_minutes: int | None = None,
    ) -> bool:
        """Stop a running task.

        Sets task status to STOPPING and signals Redis coordinator to stop.
        The Celery task will update to STOPPED when it actually stops.

        Args:
            task_id: UUID of the task to stop
            mode: Stop mode ('immediate', 'graceful', 'graceful_close', 'drain')
            drain_duration_minutes: Optional override (minutes) for drain
                timeout when ``mode == 'drain'``. When omitted the task's
                configured ``drain_duration_hours`` is used.

        Returns:
            bool: True if stop was successfully initiated, False otherwise

        Raises:
            ValueError: If task does not exist
        """

        try:
            return self.commands.stop(task_id, mode, drain_duration_minutes=drain_duration_minutes)
        except TaskValidationError:
            # Re-raise ValueError as-is (already logged)
            raise
        except ValueError as e:
            logger.error(
                f"[SERVICE:STOP] UNEXPECTED_ERROR - task_id={task_id}, error={str(e)}",
                exc_info=True,
            )
            raise ValueError(f"Failed to stop task: {str(e)}") from e
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
            self.commands.pause(task_id)

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
            cancelled = self.commands.cancel(task_id)
            if not cancelled:
                return False

            logger.info(
                "Task cancelled successfully",
                extra={"task_id": str(task_id)},
            )
            return cancelled

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
            return self.commands.restart(task_id)

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
            TaskValidationError: If the task is not in a resumable state.
            TaskServiceError: If an unexpected internal failure occurred.
        """

        logger.info("Resuming task", extra={"task_id": str(task_id)})

        try:
            task = self.commands.resume(task_id)
            logger.info("Task resumed, resubmitting", extra={"task_id": str(task_id)})
            return task

        except TaskValidationError:
            # Domain-level validation failure — message is a safe,
            # human-readable string constructed inside the service.
            raise
        except Exception as exc:
            # Anything else is an unexpected internal error.  We log the
            # full traceback but deliberately do NOT propagate the raw
            # message to callers because it may include DB driver /
            # Celery / third-party text that discloses implementation
            # details.  Callers should render a generic "try again"
            # message.
            logger.exception(
                "Unexpected error resuming task",
                extra={"task_id": str(task_id)},
            )
            raise TaskServiceError("Failed to resume task due to an internal error") from exc
