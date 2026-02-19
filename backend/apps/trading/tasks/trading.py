"""Celery tasks for live trading execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.engine import TradingEngine
from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.logging import TaskLoggingSession
from apps.trading.models import CeleryTaskStatus, TaskLog, TradingTask
from apps.trading.tasks.executor import TradingExecutor
from apps.trading.tasks.source import LiveTickDataSource
from apps.trading.utils import pip_size_for_instrument

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
    logging_session: TaskLoggingSession | None = None

    try:
        logger.info(f"Starting a new celery trading task. Task ID: {task_id}.")
        task = TradingTask.objects.get(pk=task_id)
        logging_session = TaskLoggingSession(task)
        logging_session.start()

        # Update status to RUNNING now that the task is actually executing
        logger.info(f"Transitioning: {task.status} -> RUNNING - task_id={task_id}")
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.save(update_fields=["status", "started_at", "updated_at"])
        logger.info(f"Current: RUNNING - task_id={task_id}, started_at={task.started_at}")

        # Log task start
        TaskLog.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            celery_task_id=self.request.id,
            level=LogLevel.INFO,
            component=__name__,
            message="Trading task execution started",
        )

        # Execute the trading task
        execute_trading(task)

        # Mark as stopped (trading tasks run until stopped, only if not already stopped/stopping)
        logger.info(f"Execution completed, checking final status - task_id={task_id}")
        task.refresh_from_db()
        logger.info(f"Current after execution: {task.status} - task_id={task_id}")

        if task.status not in [TaskStatus.STOPPED, TaskStatus.STOPPING]:
            logger.info(f"Transitioning: {task.status} -> STOPPED - task_id={task_id}")
            task.status = TaskStatus.STOPPED
            task.save(update_fields=["status", "updated_at"])
            logger.info(f"Current: STOPPED - task_id={task_id}")
        else:
            logger.info(f"Already in terminal state: {task.status} - task_id={task_id}")

        # Log task completion
        TaskLog.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            celery_task_id=task.celery_task_id,
            level=LogLevel.INFO,
            component=__name__,
            message="Trading task stopped successfully",
        )
    except TradingTask.DoesNotExist:
        logger.error(f"TradingTask {task_id} not found")
        raise
    except Exception as e:
        handle_exception(task_id, task, e)
        raise
    finally:
        if logging_session:
            logging_session.stop()


def execute_trading(task: TradingTask) -> None:
    """Execute a trading task.

    Args:
        task: Trading task to execute
    """

    # Resolve pip_size: use task value, or derive from instrument
    resolved_pip_size = task.pip_size or pip_size_for_instrument(task.instrument)

    # Create trading engine
    engine = TradingEngine(
        instrument=task.instrument,
        pip_size=resolved_pip_size,
        strategy_config=task.config,
    )

    # Persist pip_size back to task if it was null
    if not task.pip_size:
        task.pip_size = resolved_pip_size
        task.save(update_fields=["pip_size", "updated_at"])

    # Create data source for live ticks
    channel = f"live:{task.oanda_account.account_id}:{task.instrument}"
    data_source = LiveTickDataSource(
        channel=channel,
        instrument=task.instrument,
    )

    # Create manager
    # Create executor
    executor = TradingExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
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

        # Update CeleryTaskStatus to maintain state consistency
        from apps.trading.models.celery import CeleryTaskStatus

        CeleryTaskStatus.objects.filter(
            task_name="trading.tasks.run_trading_task",
            instance_key=str(task_id),
        ).update(
            status=CeleryTaskStatus.Status.FAILED,
            status_message=f"Task failed: {type(error).__name__}: {error_message}",
        )

        logger.info(f"CeleryTaskStatus updated to FAILED - task_id={task_id}")

        # Log error
        TaskLog.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            celery_task_id=task.celery_task_id,
            level=LogLevel.ERROR,
            component=__name__,
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
        logger.info(f"Stop task started - task_id={task_id}, mode={mode}")
        task = TradingTask.objects.get(pk=task_id)
        logger.info(f"Task loaded - task_id={task_id}, status={task.status}")

        # Handle STOPPING state (normal case)
        if task.status == TaskStatus.STOPPING:
            logger.info(f"Current: STOPPING, proceeding with stop - task_id={task_id}")
            # Revoke the Celery task if it exists
            if task.celery_task_id:
                from celery import current_app

                logger.info(
                    f"Revoking Celery task - task_id={task_id}, "
                    f"celery_task_id={task.celery_task_id}"
                )
                current_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info(
                    f"Celery task revoked - task_id={task_id}, celery_task_id={task.celery_task_id}"
                )

            # Update task status to STOPPED (without completed_at since it didn't complete)
            logger.info(f"Transitioning: {task.status} -> STOPPED - task_id={task_id}")
            task.status = TaskStatus.STOPPED
            task.save(update_fields=["status", "updated_at"])
            logger.info(f"Current: STOPPED - task_id={task_id}")

            # Update CeleryTaskStatus
            task_name = "trading.tasks.run_trading_task"
            instance_key = str(task_id)
            CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
                status=CeleryTaskStatus.Status.STOPPED,
                stopped_at=dj_timezone.now(),
                last_heartbeat_at=dj_timezone.now(),
            )

            logger.info(f"Trading task {task_id} stopped successfully (mode={mode})")

        # Handle STOPPED state (race condition - task stopped before stop task ran)
        elif task.status == TaskStatus.STOPPED:
            logger.info(f"Already STOPPED - task_id={task_id}, nothing to do")

        else:
            logger.warning(f"Unexpected state: {task.status} - task_id={task_id}")
    except TradingTask.DoesNotExist:
        logger.error(f"Trading task {task_id} not found")
        raise
