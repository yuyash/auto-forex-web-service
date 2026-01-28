"""Celery tasks for backtest execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import BacktestTask, TaskLog

logger: Logger = getLogger(name=__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_backtest_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_backtest_task(self: Any, task_id: UUID) -> None:
    """Celery task wrapper for running backtest tasks.

    Args:
        task_id: UUID of the BacktestTask to execute
    """
    task = None

    try:
        logger.info(f"Starting a new celery backtest task. Task ID: {task_id}.")
        task = BacktestTask.objects.get(pk=task_id)

        # Update status to RUNNING now that the task is actually executing
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.save(update_fields=["status", "started_at", "updated_at"])

        # Log task start
        TaskLog.objects.create(
            task=task,
            celery_task_id=self.request.id,
            level=LogLevel.INFO,
            message="Backtest task execution started",
        )

        # Execute the backtest
        execute_backtest(task)

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
    except BacktestTask.DoesNotExist:
        logger.error(f"BacktestTask {task_id} not found")
        raise
    except Exception as e:
        handle_exception(task_id, task, e)
        raise


def execute_backtest(task: BacktestTask) -> None:
    """Execute a backtest task.

    Args:
        task: Backtest task to execute
    """
    from apps.trading.services.controller import TaskController
    from apps.trading.strategies.registry import register_all_strategies, registry
    from apps.trading.tasks.executor import BacktestExecutor
    from apps.trading.tasks.source import RedisTickDataSource

    # Register all strategies
    register_all_strategies()

    # Create strategy instance
    strategy = registry.create(
        instrument=task.instrument,
        pip_size=task.pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
        trading_mode=task.trading_mode,
    )

    # Create data source - use task.pk as request_id to match publisher
    request_id = str(task.pk)
    channel = f"market:backtest:ticks:{request_id}"
    data_source = RedisTickDataSource(
        channel=channel,
        batch_size=100,
        trigger_publisher=lambda: trigger_backtest_publisher(task),
    )

    # Create controller
    controller = TaskController(
        task_name="trading.tasks.run_backtest_task",
        instance_key=str(task.pk),
        task_id=task.pk,
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


def handle_exception(task_id: UUID, task: BacktestTask | None, error: Exception) -> None:
    # Capture error details and update task
    error_message = str(error)
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
            message=f"Backtest task execution failed: {type(error).__name__}: {error_message}",
        )


def trigger_backtest_publisher(task: BacktestTask) -> None:
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


@shared_task(bind=True, name="trading.tasks.stop_backtest_task")
def stop_backtest_task(self: Any, task_id: UUID) -> None:
    """Stop a running backtest task.

    This performs the actual stop operation, updating the task to STOPPED status.

    Args:
        task_id: UUID of the backtest task to stop
    """
    from apps.trading.enums import TaskStatus

    try:
        task = BacktestTask.objects.get(pk=task_id)

        # Only stop if task is in STOPPING state
        if task.status == TaskStatus.STOPPING:
            # Revoke the Celery task if it exists
            if task.celery_task_id:
                from celery import current_app

                current_app.control.revoke(task.celery_task_id, terminate=True)

            # Update task status to STOPPED
            task.status = TaskStatus.STOPPED
            task.completed_at = dj_timezone.now()
            task.save(update_fields=["status", "completed_at", "updated_at"])

            # Update CeleryTaskStatus
            from apps.trading.models import CeleryTaskStatus

            task_name = "trading.tasks.run_backtest_task"
            instance_key = str(task_id)
            CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
                status=CeleryTaskStatus.Status.STOPPED,
                stopped_at=dj_timezone.now(),
                last_heartbeat_at=dj_timezone.now(),
            )

            logger.info(f"Backtest task {task_id} stopped successfully")
        else:
            logger.warning(
                f"Backtest task {task_id} not in STOPPING state (current: {task.status})"
            )
    except BacktestTask.DoesNotExist:
        logger.error(f"Backtest task {task_id} not found")
        raise
