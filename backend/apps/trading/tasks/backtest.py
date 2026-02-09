"""Celery tasks for backtest execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone as dj_timezone

from apps.trading.engine import TradingEngine
from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import BacktestTask, TaskLog
from apps.trading.tasks.executor import BacktestExecutor
from apps.trading.tasks.source import RedisTickDataSource

logger: Logger = getLogger(name=__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_backtest_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=7200,  # Hard limit: 2 hours
    soft_time_limit=7000,  # Soft limit: ~1 hour 56 minutes (gives 4 minutes for cleanup)
)
def run_backtest_task(self: Any, task_id: UUID) -> None:
    """Celery task wrapper for running backtest tasks.

    Args:
        task_id: UUID of the BacktestTask to execute
    """
    task = None

    try:
        logger.info(
            f"[CELERY:BACKTEST] Task started - task_id={task_id}, "
            f"celery_task_id={self.request.id}, worker={self.request.hostname}"
        )
        task = BacktestTask.objects.get(pk=task_id)

        logger.info(
            f"[CELERY:BACKTEST] Task loaded from DB - task_id={task_id}, "
            f"status={task.status}, instrument={task.instrument}, "
            f"start_time={task.start_time}, end_time={task.end_time}"
        )

        # Update status to RUNNING now that the task is actually executing
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.save(update_fields=["status", "started_at", "updated_at"])

        logger.info(
            f"[CELERY:BACKTEST] Status updated to RUNNING - task_id={task_id}, "
            f"started_at={task.started_at}"
        )

        # Log task start
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            celery_task_id=self.request.id,
            level=LogLevel.INFO,
            message="Backtest task execution started",
        )

        # Execute the backtest
        logger.info(f"[CELERY:BACKTEST] Calling execute_backtest - task_id={task_id}")
        execute_backtest(task)

        # Mark as completed
        logger.info(f"[CELERY:BACKTEST] Execution completed, updating status - task_id={task_id}")
        task.refresh_from_db()
        task.status = TaskStatus.COMPLETED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])

        # Log task completion
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            celery_task_id=task.celery_task_id,
            level=LogLevel.INFO,
            message="Backtest task completed successfully",
        )

        logger.info(
            f"[CELERY:BACKTEST] SUCCESS - task_id={task_id}, "
            f"completed_at={task.completed_at}, duration={(task.completed_at - task.started_at).total_seconds()}s"
        )

    except SoftTimeLimitExceeded:
        logger.warning(
            f"[CELERY:BACKTEST] SOFT_TIMEOUT - task_id={task_id}, celery_task_id={self.request.id}"
        )
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = dj_timezone.now()
            task.error_message = "Task exceeded time limit (soft timeout)"
            task.save(update_fields=["status", "completed_at", "error_message"])

            TaskLog.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                celery_task_id=task.celery_task_id,
                level=LogLevel.WARNING,
                message="Backtest task exceeded soft time limit",
            )
        raise

    except BacktestTask.DoesNotExist:
        logger.error(f"[CELERY:BACKTEST] TASK_NOT_FOUND - task_id={task_id}")
        raise
    except Exception as error:
        logger.error(
            f"[CELERY:BACKTEST] EXECUTION_FAILED - task_id={task_id}, error={str(error)}",
            exc_info=True,
        )
        handle_exception(task_id, task, error)
        raise


def execute_backtest(task: BacktestTask) -> None:
    """Execute a backtest task.

    Args:
        task: Backtest task to execute
    """

    logger.info(
        f"[EXECUTOR:BACKTEST] Starting execution - task_id={task.pk}, "
        f"instrument={task.instrument}, pip_size={task.pip_size}"
    )

    # Create trading engine
    logger.info(f"[EXECUTOR:BACKTEST] Creating trading engine - task_id={task.pk}")
    engine = TradingEngine(
        instrument=task.instrument,
        pip_size=task.pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
    )

    # Create data source - use task.pk as request_id to match publisher
    request_id = str(task.pk)
    channel = f"market:backtest:ticks:{request_id}"
    logger.info(
        f"[EXECUTOR:BACKTEST] Creating data source - task_id={task.pk}, "
        f"channel={channel}, request_id={request_id}"
    )
    data_source = RedisTickDataSource(
        channel=channel,
        batch_size=100,
        trigger_publisher=lambda: trigger_backtest_publisher(task),
    )

    logger.info(f"[EXECUTOR:BACKTEST] Creating executor - task_id={task.pk}")
    executor = BacktestExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
    )

    # Execute
    logger.info(f"[EXECUTOR:BACKTEST] Starting executor.execute() - task_id={task.pk}")
    executor.execute()
    logger.info(f"[EXECUTOR:BACKTEST] Executor completed - task_id={task.pk}")


def handle_exception(task_id: UUID, task: BacktestTask | None, error: Exception) -> None:
    # Capture error details and update task
    error_message = str(error)
    error_traceback = traceback.format_exc()

    logger.error(
        f"[CELERY:BACKTEST] EXCEPTION_HANDLER - task_id={task_id}, "
        f"error_type={type(error).__name__}, error={error_message}",
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

        logger.info(
            f"[CELERY:BACKTEST] Task marked as FAILED - task_id={task_id}, "
            f"completed_at={task.completed_at}"
        )

        # Log error
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
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

    logger.info(
        f"[PUBLISHER:TRIGGER] Triggering backtest publisher - task_id={task.pk}, "
        f"request_id={request_id}, instrument={task.instrument}, "
        f"start={task.start_time}, end={task.end_time}"
    )

    # Check if market worker is available
    from celery import current_app

    inspect = current_app.control.inspect()
    active_queues = inspect.active_queues()

    market_worker_available = False
    if active_queues:
        for worker, queues in active_queues.items():
            for queue_info in queues:
                if isinstance(queue_info, dict) and queue_info.get("name") == "market":
                    market_worker_available = True
                    logger.info(
                        f"[PUBLISHER:TRIGGER] Market worker found - worker={worker}, "
                        f"task_id={task.pk}"
                    )
                    break

    if not market_worker_available:
        logger.warning(
            f"[PUBLISHER:TRIGGER] NO_MARKET_WORKER - Running publisher in background thread as fallback - "
            f"task_id={task.pk}"
        )
        # Run in background thread to avoid blocking the executor
        import threading

        from apps.market.tasks.backtest import BacktestTickPublisherRunner

        def run_publisher_in_thread():
            try:
                runner = BacktestTickPublisherRunner()
                runner.run(
                    instrument=task.instrument,
                    start=task.start_time.isoformat(),
                    end=task.end_time.isoformat(),
                    request_id=request_id,
                )
                logger.info(
                    f"[PUBLISHER:TRIGGER] Background thread publisher completed - task_id={task.pk}"
                )
            except Exception as e:
                logger.error(
                    f"[PUBLISHER:TRIGGER] Background thread publisher failed - task_id={task.pk}, error={e}",
                    exc_info=True,
                )

        publisher_thread = threading.Thread(target=run_publisher_in_thread, daemon=True)
        publisher_thread.start()
        logger.info(f"[PUBLISHER:TRIGGER] Publisher thread started - task_id={task.pk}")
    else:
        # Trigger async task
        result = publish_ticks_for_backtest.delay(
            instrument=task.instrument,
            start=task.start_time.isoformat(),
            end=task.end_time.isoformat(),
            request_id=request_id,
        )
        logger.info(
            f"[PUBLISHER:TRIGGER] Publisher task submitted - task_id={task.pk}, "
            f"publisher_celery_task_id={result.id}, channel=market:backtest:ticks:{request_id}"
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
