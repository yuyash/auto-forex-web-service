"""Refactored Celery tasks using BacktestExecutor and TradingExecutor.

This module contains the refactored versions of run_backtest_task and run_trading_task
that use class-based task runners with shared functionality.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone as dj_timezone

from apps.trading.dataclasses import EventContext
from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import (
    BacktestTask,
    CeleryTaskStatus,
    TaskExecution,
    TradingTask,
)
from apps.trading.services.celery import CeleryTaskService
from apps.trading.services.events import EventEmitter
from apps.trading.services.executor import BacktestExecutor, TradingExecutor
from apps.trading.services.lifecycle import ExecutionLifecycle, StrategyCreationContext
from apps.trading.services.registry import register_all_strategies
from apps.trading.services.source import LiveTickDataSource, RedisTickDataSource

logger: Logger = getLogger(name=__name__)


class BaseTaskRunner(ABC):
    """Base class for task runners with common functionality."""

    # Instance attributes set during run() execution
    execution: TaskExecution
    task: BacktestTask | TradingTask
    event_emitter: EventEmitter
    task_service: CeleryTaskService

    def __init__(self) -> None:
        """Initialize the task runner."""
        register_all_strategies()

    @staticmethod
    def _create_execution(*, task_type: str, task_id: int) -> TaskExecution:
        """Create a new TaskExecution with sequential numbering."""
        last_num = (
            TaskExecution.objects.filter(task_type=task_type, task_id=task_id)
            .order_by("-execution_number")
            .values_list("execution_number", flat=True)
            .first()
        )
        next_num = int(last_num or 0) + 1
        return TaskExecution.objects.create(
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
    ) -> TaskExecution:
        """Get existing execution or create a new one.

        Args:
            task_type: Type of task (BACKTEST or TRADING)
            task_id: ID of the task
            execution_id: Optional ID of existing execution to resume

        Returns:
            TaskExecution instance
        """
        execution: TaskExecution
        if execution_id is not None:
            try:
                execution = TaskExecution.objects.get(
                    pk=int(execution_id),
                    task_type=task_type.value,
                    task_id=task_id,
                )
                if execution.status != TaskStatus.RUNNING or execution.progress != 0:
                    execution.status = TaskStatus.RUNNING
                    execution.progress = 0
                if execution.started_at is None:
                    execution.started_at = dj_timezone.now()
                execution.save(update_fields=["status", "progress", "started_at"])
            except TaskExecution.DoesNotExist:
                execution = self._create_execution(task_type=task_type.value, task_id=task_id)
        else:
            execution = self._create_execution(task_type=task_type.value, task_id=task_id)
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


class BacktestTaskRunner(BaseTaskRunner):
    """Task runner for backtest tasks."""

    @staticmethod
    def _backtest_channel_for_request(request_id: str) -> str:
        """Get the Redis channel name for a backtest request."""
        prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
        return f"{prefix}{request_id}"

    def _create_data_source(self) -> RedisTickDataSource:
        """Create data source for backtest execution."""
        # Type assertion for BacktestTask
        assert isinstance(self.task, BacktestTask), "Task must be BacktestTask"

        task_id = self.task.pk
        request_id = f"backtest:{task_id}:{int(time.time())}"
        channel = self._backtest_channel_for_request(request_id)

        start = self._isoformat(self.task.start_time)
        end = self._isoformat(self.task.end_time)
        instrument = self.task.instrument

        def trigger_publisher() -> None:
            """Trigger the market service to publish ticks."""
            from apps.market.tasks import publish_ticks_for_backtest

            publish_ticks_for_backtest.delay(  # type: ignore[attr-defined]
                instrument=instrument,
                start=start,
                end=end,
                request_id=request_id,
            )
            logger.info(
                f"Backtest data source enqueued tick publisher (request_id={request_id}, "
                f"instrument={instrument}, start={start}, end={end})"
            )

        return RedisTickDataSource(
            channel=channel,
            batch_size=100,
            trigger_publisher=trigger_publisher,
        )

    def _create_executor(self, data_source: RedisTickDataSource, strategy: Any) -> BacktestExecutor:
        """Create BacktestExecutor instance."""
        # Type assertion for BacktestTask
        assert isinstance(self.task, BacktestTask), "Task must be BacktestTask"

        return BacktestExecutor(
            data_source=data_source,
            strategy=strategy,
            execution=self.execution,
            task=self.task,
        )

    @shared_task(bind=True, name="trading.tasks.run_backtest_task")
    def run(self, task_id: int, execution_id: int | None = None) -> None:
        """Run a backtest task using BacktestExecutor."""
        # Initialize Celery task service
        self._initialize_task_service(
            task_name="trading.tasks.run_backtest_task",
            task_id=task_id,
            kind="backtest",
        )

        logger.info(f"Backtest task started (task_id={task_id})")

        try:
            # Load the backtest task
            self.task: BacktestTask = BacktestTask.objects.select_related("config", "user").get(
                pk=task_id
            )
        except BacktestTask.DoesNotExist:
            logger.error(f"BacktestTask {task_id} not found")
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.FAILED, status_message="Task not found"
            )
            return

        # Setup execution context
        self._setup_execution_context(
            task_id=task_id,
            execution_id=execution_id,
            task_type=TaskType.BACKTEST,
            log_message="Backtest execution started",
        )

        # Create strategy with automatic error handling
        with StrategyCreationContext(
            execution=self.execution,
            task=self.task,
            event_emitter=self.event_emitter,
            task_service=self.task_service,
            strategy_config=self.task.config,
        ) as strategy_ctx:
            strategy = strategy_ctx.create_strategy()
            if strategy is None:
                return  # Error was handled by context manager

        # Create data source and executor
        data_source = self._create_data_source()
        executor = self._create_executor(data_source, strategy)

        # Execute with lifecycle management
        with ExecutionLifecycle(
            execution=self.execution,
            task=self.task,
            event_emitter=self.event_emitter,
            task_service=self.task_service,
            success_status=TaskStatus.COMPLETED,
        ) as lifecycle:
            lifecycle.set_strategy_type(self.task.config.strategy_type)
            executor.execute()


class TradingTaskRunner(BaseTaskRunner):
    """Task runner for live trading tasks."""

    def _create_data_source(self) -> LiveTickDataSource:
        """Create data source for live trading execution."""
        channel = settings.MARKET_TICK_CHANNEL
        return LiveTickDataSource(
            channel=channel,
            instrument=self.task.instrument,
        )

    def _create_executor(self, data_source: LiveTickDataSource, strategy: Any) -> TradingExecutor:
        """Create TradingExecutor instance."""
        # Type assertion for TradingTask
        assert isinstance(self.task, TradingTask), "Task must be TradingTask"

        from apps.market.services.oanda import OandaService

        trading_ops = OandaService(account=self.task.oanda_account)

        return TradingExecutor(
            data_source=data_source,
            strategy=strategy,
            trading_ops=trading_ops,
            execution=self.execution,
            task=self.task,
        )

    @shared_task(bind=True, name="trading.tasks.run_trading_task")
    def run(self, task_id: int, execution_id: int | None = None) -> None:
        """Run a live trading task using TradingExecutor."""
        # Initialize Celery task service
        self._initialize_task_service(
            task_name="trading.tasks.run_trading_task",
            task_id=task_id,
            kind="trading",
        )

        logger.info(f"Trading task started (task_id={task_id})")

        try:
            # Load the trading task
            self.task: TradingTask = TradingTask.objects.select_related(
                "config", "oanda_account", "user"
            ).get(pk=task_id)
        except TradingTask.DoesNotExist:
            logger.error(f"TradingTask {task_id} not found")
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.FAILED, status_message="Task not found"
            )
            return

        # Setup execution context
        self._setup_execution_context(
            task_id=task_id,
            execution_id=execution_id,
            task_type=TaskType.TRADING,
            log_message="Trading execution started",
        )

        # Create strategy with automatic error handling
        with StrategyCreationContext(
            execution=self.execution,
            task=self.task,
            event_emitter=self.event_emitter,
            task_service=self.task_service,
            strategy_config=self.task.config,
        ) as strategy_ctx:
            strategy = strategy_ctx.create_strategy()
            if strategy is None:
                return  # Error was handled by context manager

        # Create data source and executor
        data_source = self._create_data_source()
        executor = self._create_executor(data_source, strategy)

        # Execute with lifecycle management
        with ExecutionLifecycle(
            execution=self.execution,
            task=self.task,
            event_emitter=self.event_emitter,
            task_service=self.task_service,
            success_status=TaskStatus.STOPPED,  # Trading tasks stop, not complete
        ) as lifecycle:
            lifecycle.set_strategy_type(self.task.config.strategy_type)
            executor.execute()

    @shared_task(bind=True, name="trading.tasks.stop_trading_task")
    def stop(self, task_id: int, mode: str = "graceful") -> None:
        """Request stop for a running trading task.

        This handles complex cleanup operations like closing positions.
        Backtest tasks use a simpler direct stop mechanism via
        TaskLockManager.set_cancellation_flag().

        Args:
            task_id: ID of the trading task to stop
            mode: Stop mode ('immediate', 'graceful', 'graceful_close')
        """
        task_name = "trading.tasks.run_trading_task"
        instance_key = str(task_id)
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
            status=CeleryTaskStatus.Status.STOP_REQUESTED,
            status_message=f"stop_requested mode={mode}",
            last_heartbeat_at=dj_timezone.now(),
        )

        logger.info(f"Stop requested for trading task {task_id} (mode={mode})")


# Create singleton instances
backtest_runner = BacktestTaskRunner()
trading_runner = TradingTaskRunner()

# Export task functions for Celery autodiscovery
run_backtest_task = backtest_runner.run
run_trading_task = trading_runner.run
stop_trading_task = trading_runner.stop
