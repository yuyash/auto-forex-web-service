"""Execution lifecycle management for tasks.

This module provides context managers and utilities for managing
the lifecycle of task executions, including status transitions,
event emission, and error handling.
"""

from __future__ import annotations

from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any

from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfig

from apps.trading.models import BacktestTask, TaskExecution, TradingTask
from apps.trading.services.celery import CeleryTaskService
from apps.trading.services.events import EventEmitter

logger: Logger = getLogger(name=__name__)


class StrategyCreationContext:
    """Context manager for strategy creation with automatic error handling.

    Automatically handles:
    - Logging strategy creation
    - Error handling and cleanup on failure
    - Status updates for task and execution
    - Event emission

    Example:
        with StrategyCreationContext(
            execution=execution,
            task=task,
            event_emitter=event_emitter,
            task_service=task_service,
            strategy_config=task.config,
        ) as ctx:
            strategy = ctx.create_strategy()
            if strategy is None:
                return  # Error was handled
    """

    def __init__(
        self,
        *,
        execution: TaskExecution,
        task: BacktestTask | TradingTask,
        event_emitter: EventEmitter,
        task_service: CeleryTaskService,
        strategy_config: "StrategyConfig",
    ) -> None:
        """Initialize the strategy creation context.

        Args:
            execution: TaskExecution instance
            task: Task instance (BacktestTask or TradingTask)
            event_emitter: EventEmitter for error events
            task_service: CeleryTaskService for lifecycle management
            strategy_config: StrategyConfig model instance
        """
        self.execution = execution
        self.task: BacktestTask | TradingTask = task
        self.event_emitter = event_emitter
        self.task_service = task_service
        self.strategy_config = strategy_config
        self.strategy: Any = None
        self._error_occurred = False

    def __enter__(self) -> StrategyCreationContext:
        """Enter the context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the context and handle any errors.

        Returns:
            True to suppress exception (error was handled), False to propagate
        """
        if exc_type is not None and not self._error_occurred:
            # An unhandled exception occurred
            self._handle_creation_error(exc_val)
            return True  # Suppress exception (we handled it)

        return False  # No exception or already handled

    def create_strategy(self) -> Any:
        """Create strategy from config.

        Returns:
            Strategy instance or None if creation failed
        """
        try:
            from apps.trading.services.registry import registry as strategy_registry

            # Get instrument and pip_size from task
            instrument = self.task.instrument
            pip_size = self.task.pip_size

            self.strategy = strategy_registry.create(
                instrument=instrument,
                pip_size=pip_size,
                strategy_config=self.strategy_config,
            )

            logger.info(f"Strategy created (strategy_type={self.strategy_config.strategy_type})")
            self.execution.add_log(
                LogLevel.INFO, f"Strategy created: {self.strategy_config.strategy_type}"
            )

            return self.strategy

        except Exception as e:
            self._handle_creation_error(e)
            return None

    def _handle_creation_error(self, exc: BaseException | None) -> None:
        """Handle strategy creation error.

        Args:
            exc: Exception that occurred
        """
        if exc is None or not isinstance(exc, Exception):
            exc = Exception(str(exc) if exc else "Unknown error")

        self._error_occurred = True
        error_msg = str(exc)

        self.execution.add_log(LogLevel.ERROR, f"Strategy creation failed: {error_msg}")
        self.execution.status = TaskStatus.FAILED
        self.execution.completed_at = dj_timezone.now()
        self.execution.save(update_fields=["status", "completed_at"])

        self.task.status = TaskStatus.FAILED
        self.task.save(update_fields=["status"])

        from apps.trading.models import CeleryTaskStatus

        self.task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED, status_message=error_msg
        )

        self.event_emitter.emit_error(
            error=exc,
            error_context={
                "phase": "strategy_creation",
                "strategy_type": self.strategy_config.strategy_type,
                "error_message": error_msg,
            },
        )

        logger.error(f"Task failed during strategy creation: {error_msg}")


class ExecutionLifecycle:
    """Context manager for handling task execution lifecycle.

    Automatically manages:
    - Status transitions (PENDING -> RUNNING -> COMPLETED/FAILED)
    - Event emission for status changes
    - Task and execution status updates
    - CeleryTaskService lifecycle
    - Error handling and cleanup

    Example:
        with ExecutionLifecycle(
            execution=execution,
            task=task,
            event_emitter=event_emitter,
            task_service=task_service,
            success_status=TaskStatus.COMPLETED,
        ) as lifecycle:
            executor.execute()
    """

    def __init__(
        self,
        *,
        execution: TaskExecution,
        task: BacktestTask | TradingTask,
        event_emitter: EventEmitter,
        task_service: CeleryTaskService,
        success_status: TaskStatus = TaskStatus.COMPLETED,
        failure_status: TaskStatus = TaskStatus.FAILED,
        start_from_status: str = "PENDING",
        running_status: str = "RUNNING",
    ) -> None:
        """Initialize the execution lifecycle manager.

        Args:
            execution: TaskExecution instance
            task: Task instance (BacktestTask or TradingTask)
            event_emitter: EventEmitter for status events
            task_service: CeleryTaskService for lifecycle management
            success_status: Status to set on successful completion
            failure_status: Status to set on failure
            start_from_status: Initial status name for event emission
            running_status: Running status name for event emission
        """
        self.execution = execution
        self.task = task
        self.event_emitter = event_emitter
        self.task_service = task_service
        self.success_status = success_status
        self.failure_status = failure_status
        self.start_from_status = start_from_status
        self.running_status = running_status
        self.strategy_type: str | None = None

    def set_strategy_type(self, strategy_type: str) -> None:
        """Set the strategy type for error context.

        Args:
            strategy_type: Strategy type identifier
        """
        self.strategy_type = strategy_type

    def __enter__(self) -> ExecutionLifecycle:
        """Enter the execution context.

        Emits status change event from start_from_status to RUNNING.
        """
        # Emit status change event
        self.event_emitter.emit_status_changed(
            from_status=self.start_from_status,
            to_status=self.running_status,
            reason="Execution started",
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the execution context.

        Handles both successful completion and exceptions:
        - On success: Updates status to success_status, emits completion event
        - On exception: Updates status to failure_status, emits error and failure events

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            False to propagate exceptions (never suppresses exceptions)
        """
        if exc_type is None:
            # Success path
            self._handle_success()
        else:
            # Failure path
            self._handle_failure(exc_val)

        # Always propagate exceptions
        return False

    def _handle_success(self) -> None:
        """Handle successful execution completion."""
        # Mark task as completed
        self.task.status = self.success_status
        self.task.save(update_fields=["status", "updated_at"])

        # Emit status change event
        success_status_name = self.success_status.value.upper()
        self.event_emitter.emit_status_changed(
            from_status=self.running_status,
            to_status=success_status_name,
            reason="Execution completed successfully",
        )

        # Mark Celery task as stopped
        from apps.trading.models import CeleryTaskStatus

        self.task_service.mark_stopped(
            status=CeleryTaskStatus.Status.COMPLETED
            if self.success_status == TaskStatus.COMPLETED
            else CeleryTaskStatus.Status.STOPPED,
            status_message="Execution completed successfully",
        )

        task_id = self.task.id if hasattr(self.task, "id") else "unknown"
        logger.info(f"Task completed successfully (task_id={task_id})")

    def _handle_failure(self, exc: BaseException | None) -> None:
        """Handle execution failure.

        Args:
            exc: Exception that caused the failure
        """
        # Convert BaseException to Exception for compatibility
        if exc is None or not isinstance(exc, Exception):
            exc = Exception(str(exc) if exc else "Unknown error")

        logger.exception(f"Task crashed: {exc}")

        # Emit error event
        error_context: dict[str, Any] = {"phase": "execution"}
        if self.strategy_type:
            error_context["strategy_type"] = self.strategy_type

        self.event_emitter.emit_error(
            error=exc,
            error_context=error_context,
        )

        # Emit status change event
        self.event_emitter.emit_status_changed(
            from_status=self.running_status,
            to_status=self.failure_status.value.upper(),
            reason=str(exc),
        )

        # Mark execution as failed
        self.execution.mark_failed(exc)

        # Mark task as failed
        self.task.status = self.failure_status
        self.task.save(update_fields=["status", "updated_at"])

        # Mark Celery task as stopped
        from apps.trading.models import CeleryTaskStatus

        self.task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED, status_message=str(exc)
        )
