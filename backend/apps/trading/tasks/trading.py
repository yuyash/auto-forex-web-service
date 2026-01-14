from __future__ import annotations

from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import (
    CeleryTaskStatus,
    TradingTask,
)
from apps.trading.services.executor import TradingExecutor
from apps.trading.services.lifecycle import ExecutionLifecycle, StrategyCreationContext
from apps.trading.services.source import LiveTickDataSource
from apps.trading.tasks.base import BaseTaskRunner

logger: Logger = getLogger(name=__name__)


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

        trading_service = OandaService(account=self.task.oanda_account)

        return TradingExecutor(
            data_source=data_source,
            strategy=strategy,
            trading_service=trading_service,
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

        logger.info(f"Trading task started (task_id={task_id}, execution_id={execution_id})")

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

        # Setup execution context (with stale execution check)
        try:
            self._setup_execution_context(
                task_id=task_id,
                execution_id=execution_id,
                task_type=TaskType.TRADING,
                log_message="Trading execution started",
            )
        except ValueError as e:
            # Stale execution detected - skip this task
            logger.warning(
                "Skipping stale trading execution: task_id=%d, execution_id=%s, reason=%s",
                task_id,
                execution_id,
                str(e),
            )
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.FAILED,
                status_message=f"Stale execution skipped: {str(e)}",
            )
            return

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
