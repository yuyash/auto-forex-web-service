"""Celery tasks for live trading execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import CeleryTaskStatus, TaskLog, TradingTasks

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
        task_id: UUID of the TradingTasks to execute
    """
    task = None

    try:
        logger.info(f"Starting a new celery trading task. Task ID: {task_id}.")
        task = TradingTasks.objects.get(pk=task_id)
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.celery_task_id = self.request.id
        task.save(update_fields=["status", "started_at", "celery_task_id"])

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
    except TradingTasks.DoesNotExist:
        logger.error(f"TradingTasks {task_id} not found")
        raise
    except Exception as e:
        handle_exception(task_id, task, e)
        raise


def execute_trading(task: TradingTasks) -> None:
    """Execute a trading task.

    Args:
        task: Trading task to execute
    """
    from apps.trading.services.controller import TaskController
    from apps.trading.services.executor import TradingExecutor
    from apps.trading.services.registry import register_all_strategies, registry
    from apps.trading.services.source import LiveTickDataSource

    # Register all strategies
    register_all_strategies()

    # Create strategy instance
    strategy = registry.create(
        instrument=task.instrument,
        pip_size=task.pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
        trading_mode=task.trading_mode,
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
    )

    # Create executor
    executor = TradingExecutor(
        task=task,
        strategy=strategy,
        data_source=data_source,
        controller=controller,
    )

    # Execute
    executor.execute()


def handle_exception(task_id: UUID, task: TradingTasks | None, error: Exception) -> None:
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
    """Request stop for a running trading task.

    This handles complex cleanup operations like closing positions.

    Args:
        task_id: UUID of the trading task to stop
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
