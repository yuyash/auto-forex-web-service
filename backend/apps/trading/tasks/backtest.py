"""Celery tasks for backtest execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import BacktestTasks, TaskLog

logger: Logger = getLogger(__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_backtest_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_backtest_task(self: Any, task_id: UUID, execution_id: int | None = None) -> None:
    """Celery task wrapper for running backtest tasks.

    Args:
        task_id: UUID of the BacktestTasks to execute
        execution_id: Deprecated parameter (ignored)
    """
    task = None

    try:
        # Load the task to update it
        task = BacktestTasks.objects.get(pk=task_id)

        # Update task status to RUNNING and record start time
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.celery_task_id = self.request.id
        task.save(update_fields=["status", "started_at", "celery_task_id"])

        # Log task start
        TaskLog.objects.create(
            task=task,
            celery_task_id=self.request.id,
            level=LogLevel.INFO,
            message="Backtest task execution started",
        )

        # Execute the backtest
        _execute_backtest(task)

        # Mark as completed
        task.refresh_from_db()
        task.status = TaskStatus.COMPLETED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at"])

        # Log task completion
        TaskLog.objects.create(
            task=task,
            celery_task_id=task.celery_task_id,
            level=LogLevel.INFO,
            message="Backtest task completed successfully",
        )

    except BacktestTasks.DoesNotExist:
        logger.error(f"BacktestTasks {task_id} not found")
        raise

    except Exception as e:
        # Capture error details and update task
        error_message = str(e)
        error_traceback = traceback.format_exc()

        logger.error(
            f"Backtest task {task_id} failed: {error_message}",
            exc_info=True,
        )

        if task:
            # Update task with error information
            task.status = TaskStatus.FAILED
            task.completed_at = dj_timezone.now()
            task.error_message = error_message
            task.error_traceback = error_traceback
            task.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "error_traceback",
                ]
            )

            # Log error
            TaskLog.objects.create(
                task=task,
                celery_task_id=task.celery_task_id,
                level=LogLevel.ERROR,
                message=f"Backtest task execution failed: {type(e).__name__}: {error_message}",
            )

        # Re-raise to trigger Celery retry
        raise


def _execute_backtest(task: BacktestTasks) -> None:
    """Execute a backtest task.

    Args:
        task: Backtest task to execute
    """
    from apps.trading.services.controller import TaskController
    from apps.trading.services.executor import BacktestExecutor
    from apps.trading.services.registry import register_all_strategies, registry
    from apps.trading.services.source import RedisTickDataSource

    # Register all strategies
    register_all_strategies()

    # Create strategy instance
    strategy = registry.create(
        instrument=task.instrument,
        pip_size=task._pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
        trading_mode=task.trading_mode,
    )

    # Create data source - use task.pk as request_id to match publisher
    request_id = str(task.pk)
    channel = f"market:backtest:ticks:{request_id}"
    data_source = RedisTickDataSource(
        channel=channel,
        batch_size=100,
        trigger_publisher=lambda: _trigger_backtest_publisher(task),
    )

    # Create controller
    controller = TaskController(
        task_name="trading.tasks.run_backtest_task",
        instance_key=str(task.pk),
    )

    # Create executor
    executor = BacktestExecutor(
        task=task,
        strategy=strategy,
        data_source=data_source,
        controller=controller,
    )

    # Execute
    executor.execute()


def _trigger_backtest_publisher(task: BacktestTasks) -> None:
    """Trigger the backtest data publisher.

    Args:
        task: Backtest task
    """
    from apps.market.tasks import publish_ticks_for_backtest

    # Use task.pk as the request_id to match the channel
    request_id = str(task.pk)

    # Trigger async task to publish ticks
    publish_ticks_for_backtest.delay(
        instrument=task.instrument,
        start=task.start_time.isoformat(),
        end=task.end_time.isoformat(),
        request_id=request_id,
    )
