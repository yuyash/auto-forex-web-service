from __future__ import annotations

import time
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import (
    BacktestTasks,
    CeleryTaskStatus,
)
from apps.trading.services.executor import BacktestExecutor
from apps.trading.services.lifecycle import ExecutionLifecycle, StrategyCreationContext
from apps.trading.services.source import RedisTickDataSource
from apps.trading.tasks.base import BaseTaskRunner

logger: Logger = getLogger(name=__name__)


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
        assert isinstance(self.task, BacktestTasks), "Task must be BacktestTask"

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
        assert isinstance(self.task, BacktestTasks), "Task must be BacktestTask"

        return BacktestExecutor(
            data_source=data_source,
            strategy=strategy,
            execution=self.execution,
            task=self.task,
        )

    def run(self, task_id: int, execution_id: int | None = None) -> None:
        """Run a backtest task using BacktestExecutor."""
        # Initialize Celery task service
        self._initialize_task_service(
            task_name="trading.tasks.run_backtest_task",
            task_id=task_id,
            kind="backtest",
        )

        logger.info(f"Backtest task started (task_id={task_id}, execution_id={execution_id})")

        try:
            # Load the backtest task
            self.task: BacktestTasks = BacktestTasks.objects.select_related("config", "user").get(
                pk=task_id
            )
        except BacktestTasks.DoesNotExist:
            logger.error(f"BacktestTask {task_id} not found")
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.FAILED, status_message="Task not found"
            )
            return

        # Setup execution context (with stale execution check)
        try:
            self._setup_execution_context(
                task_id=task_id,
                execution_id=execution_id,
                task_type=TaskType.BACKTEST,
                log_message="Backtest execution started",
            )
        except ValueError as e:
            # Stale execution detected - skip this task
            logger.warning(
                "Skipping stale backtest execution: task_id=%d, execution_id=%s, reason=%s",
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
            success_status=TaskStatus.COMPLETED,
        ) as lifecycle:
            lifecycle.set_strategy_type(self.task.config.strategy_type)
            executor.execute()


# Create a wrapper function that Celery can call
@shared_task(bind=True, name="trading.tasks.run_backtest_task")
def _run_backtest_task_wrapper(self: Any, task_id: int, execution_id: int | None = None) -> None:
    """Celery task wrapper for running backtest tasks."""
    runner = BacktestTaskRunner()
    runner.run(task_id, execution_id)
