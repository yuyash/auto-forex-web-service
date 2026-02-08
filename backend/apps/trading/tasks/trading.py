"""Celery tasks for live trading execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import CeleryTaskStatus, TaskLog, TradingTask

logger: Logger = getLogger(name=__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_trading_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_trading_task(self: Any, task_id: UUID) -> None:
    """Celery task wrapper for running trading tasks.

    Args:
        task_id: UUID of the TradingTask to execute
    """
    task = None

    try:
        logger.info(f"Starting a new celery trading task. Task ID: {task_id}.")
        task = TradingTask.objects.get(pk=task_id)

        # Update status to RUNNING now that the task is actually executing
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.save(update_fields=["status", "started_at", "updated_at"])

        # Log task start
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Trading task execution started",
        )

        # Execute the trading task
        execute_trading(task)

        # Mark as stopped (trading tasks run until stopped)
        task.refresh_from_db()
        task.status = TaskStatus.STOPPED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at"])

        # Log task completion
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Trading task stopped successfully",
        )
    except TradingTask.DoesNotExist:
        logger.error(f"TradingTask {task_id} not found")
        raise
    except Exception as e:
        handle_exception(task_id, task, e)
        raise


def execute_trading(task: TradingTask) -> None:
    """Execute a trading task.

    Args:
        task: Trading task to execute
    """
    from apps.trading.services.controller import TaskController
    from apps.trading.services.engine import TradingEngine
    from apps.trading.tasks.executor import TradingExecutor
    from apps.trading.tasks.source import LiveTickDataSource

    # Create trading engine
    engine = TradingEngine(
        instrument=task.instrument,
        pip_size=task.pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
    )

    # Create data source for live ticks
    channel = f"live:{task.oanda_account.account_id}:{task.instrument}"
    data_source = LiveTickDataSource(
        channel=channel,
        instrument=task.instrument,
    )

    # Create controller
    controller = TaskController(
        task_name="trading.tasks.run_trading_task",
        instance_key=str(task.pk),
        task_id=task.pk,
    )

    # Create executor
    executor = TradingExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
        controller=controller,
    )

    # Execute
    executor.execute()


def handle_exception(task_id: UUID, task: TradingTask | None, error: Exception) -> None:
    # Capture error details and update task
    error_message = str(error)
    error_traceback = traceback.format_exc()

    logger.error(
        f"Trading task {task_id} failed: {error_message}",
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
            level=LogLevel.ERROR,
            message=f"Trading task execution failed: {type(error).__name__}: {error_message}",
        )


@shared_task(bind=True, name="trading.tasks.stop_trading_task")
def stop_trading_task(self: Any, task_id: UUID, mode: str = "graceful") -> None:
    """Stop a running trading task.

    This performs the actual stop operation, updating the task to STOPPED status.

    Args:
        task_id: UUID of the trading task to stop
        mode: Stop mode ('immediate', 'graceful', 'graceful_close')
    """
    from apps.trading.enums import TaskStatus

    try:
        task = TradingTask.objects.get(pk=task_id)

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
            task_name = "trading.tasks.run_trading_task"
            instance_key = str(task_id)
            CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
                status=CeleryTaskStatus.Status.STOPPED,
                stopped_at=dj_timezone.now(),
                last_heartbeat_at=dj_timezone.now(),
            )

            logger.info(f"Trading task {task_id} stopped successfully (mode={mode})")
        else:
            logger.warning(f"Trading task {task_id} not in STOPPING state (current: {task.status})")
    except TradingTask.DoesNotExist:
        logger.error(f"Trading task {task_id} not found")
        raise
