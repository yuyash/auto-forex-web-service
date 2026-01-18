from __future__ import annotations

from abc import ABC, abstractmethod
from logging import Logger, getLogger
from typing import Any

from django.utils import timezone as dj_timezone

from apps.trading.dataclasses import EventContext
from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import (
    BacktestTasks,
    Executions,
    TradingTasks,
)
from apps.trading.services.celery import CeleryTaskService
from apps.trading.services.events import EventEmitter
from apps.trading.services.registry import register_all_strategies

logger: Logger = getLogger(name=__name__)


class BaseTaskRunner(ABC):
    """Base class for task runners with common functionality."""

    # Instance attributes set during run() execution
    execution: Executions
    task: BacktestTasks | TradingTasks
    event_emitter: EventEmitter
    task_service: CeleryTaskService

    def __init__(self) -> None:
        """Initialize the task runner."""
        register_all_strategies()

    @staticmethod
    def _create_execution(*, task_type: str, task_id: int) -> Executions:
        """Create a new Executions with sequential numbering."""
        last_num = (
            Executions.objects.filter(task_type=task_type, task_id=task_id)
            .order_by("-execution_number")
            .values_list("execution_number", flat=True)
            .first()
        )
        next_num = int(last_num or 0) + 1
        return Executions.objects.create(
            task_type=task_type,
            task_id=task_id,
            execution_number=next_num,
            status=TaskStatus.RUNNING,
            progress=0,
            started_at=dj_timezone.now(),
        )

    @staticmethod
    def _isoformat(dt: Any) -> str:
        """Convert datetime to ISO format string.

        Args:
            dt: Datetime object to convert

        Returns:
            ISO format string with 'Z' suffix
        """
        from datetime import UTC

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _get_celery_task_id(self_obj: Any) -> str | None:
        """Get Celery task ID from request context.

        Args:
            self_obj: The task instance (with bind=True)

        Returns:
            Celery task ID or None
        """
        if hasattr(self_obj, "request"):
            request = getattr(self_obj, "request")
            if hasattr(request, "id"):
                return str(request.id)
        return None

    def _get_or_create_execution(
        self,
        *,
        task_type: TaskType,
        task_id: int,
        execution_id: int | None,
    ) -> Executions:
        """Get existing execution or create a new one.

        Args:
            task_type: Type of task (BACKTEST or TRADING)
            task_id: ID of the task
            execution_id: Optional ID of existing execution to resume

        Returns:
            Executions instance

        Raises:
            ValueError: If execution_id is provided but is not the latest execution
        """
        execution: Executions

        # Get the latest execution for this task
        latest_execution = (
            Executions.objects.filter(
                task_type=task_type.value,
                task_id=task_id,
            )
            .order_by("-execution_number")
            .first()
        )

        if execution_id is not None:
            try:
                execution = Executions.objects.get(
                    pk=int(execution_id),
                    task_type=task_type.value,
                    task_id=task_id,
                )

                # Check if this is the latest execution
                if latest_execution and execution.pk != latest_execution.pk:
                    logger.warning(
                        "Skipping execution %d for task %d: not the latest execution (latest=%d)",
                        execution.pk,
                        task_id,
                        latest_execution.pk,
                    )
                    raise ValueError(
                        f"Execution {execution_id} is not the latest execution for task {task_id}. "
                        f"Latest execution is {latest_execution.pk}. Skipping to prevent stale execution."
                    )

                if execution.status != TaskStatus.RUNNING or execution.progress != 0:
                    execution.status = TaskStatus.RUNNING
                    execution.progress = 0
                if execution.started_at is None:
                    execution.started_at = dj_timezone.now()
                execution.save(update_fields=["status", "progress", "started_at"])

                logger.info(
                    "Resuming execution %d for task %d (latest execution confirmed)",
                    execution.pk,
                    task_id,
                )
            except Executions.DoesNotExist:
                logger.warning(
                    "Execution %d not found for task %d, creating new execution",
                    execution_id,
                    task_id,
                )
                execution = self._create_execution(task_type=task_type.value, task_id=task_id)
        else:
            execution = self._create_execution(task_type=task_type.value, task_id=task_id)
            logger.info(
                "Created new execution %d for task %d (execution_number=%d)",
                execution.pk,
                task_id,
                execution.execution_number,
            )

        return execution

    def _initialize_task_service(
        self,
        *,
        task_name: str,
        task_id: int,
        kind: str,
    ) -> None:
        """Initialize and start the Celery task service.

        Args:
            task_name: Full Celery task name
            task_id: Task ID
            kind: Task kind ('backtest' or 'trading')
        """
        instance_key = str(task_id)
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=1.0,
            heartbeat_interval_seconds=5.0,
        )

        celery_task_id = self._get_celery_task_id(self)

        self.task_service.start(
            celery_task_id=celery_task_id,
            worker=f"{task_id}",
            meta={"kind": kind, "task_id": task_id},
        )

    def _setup_execution_context(
        self,
        *,
        task_id: int,
        execution_id: int | None,
        task_type: TaskType,
        log_message: str,
    ) -> bool:
        """Setup execution context (task, execution, event_emitter).

        Sets the following instance attributes:
        - self.task
        - self.execution
        - self.event_emitter

        Args:
            task_id: Task ID
            execution_id: Optional execution ID to resume
            task_type: Type of task (BACKTEST or TRADING)
            log_message: Log message for execution start

        Returns:
            True if setup successful, False if task not found
        """
        # Create or load execution
        self.execution = self._get_or_create_execution(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
        )

        self.execution.add_log(LogLevel.INFO, log_message)

        # Create EventContext for event emission
        event_context = EventContext(
            execution=self.execution,
            user=self.task.user,
            account=getattr(self.task, "oanda_account", None),
            instrument=self.task.instrument,
        )
        self.event_emitter = EventEmitter(context=event_context)

        return True

    @abstractmethod
    def _create_data_source(self) -> Any:
        """Create data source for the task.

        Returns:
            Data source instance (RedisTickDataSource or LiveTickDataSource)
        """
        pass

    @abstractmethod
    def _create_executor(self, data_source: Any, strategy: Any) -> Any:
        """Create executor for the task.

        Args:
            data_source: Data source instance
            strategy: Strategy instance

        Returns:
            Executor instance (BacktestExecutor or TradingExecutor)
        """
        pass
        """Get the error message for account-related errors."""
        pass

    @abstractmethod
    def run(self, task_id: int, execution_id: int | None = None) -> None:
        """Run the task."""
        pass
