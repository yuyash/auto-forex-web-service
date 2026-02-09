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
        logger.info(
            f"[CELERY:BACKTEST] [STATUS] Transitioning: {task.status} -> RUNNING - task_id={task_id}"
        )
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.save(update_fields=["status", "started_at", "updated_at"])

        logger.info(
            f"[CELERY:BACKTEST] [STATUS] Current: RUNNING - task_id={task_id}, "
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
        logger.info(
            f"[CELERY:BACKTEST] ========== CALLING execute_backtest - task_id={task_id} =========="
        )
        execute_backtest(task)
        logger.info(
            f"[CELERY:BACKTEST] ========== execute_backtest RETURNED - task_id={task_id} =========="
        )

        # Check if task was stopped during execution
        logger.info(f"[CELERY:BACKTEST] Checking final status - task_id={task_id}")
        task.refresh_from_db()
        logger.info(
            f"[CELERY:BACKTEST] [STATUS] Current after execution: {task.status} - task_id={task_id}"
        )

        # If task is in STOPPING or STOPPED state, don't mark as completed
        if task.status in [TaskStatus.STOPPED, TaskStatus.STOPPING]:
            logger.info(
                f"[CELERY:BACKTEST] [STATUS] Task was stopped during execution, not marking as completed - "
                f"task_id={task_id}, status={task.status}"
            )
            return

        # Mark as completed (only if not already stopped or stopping)
        logger.info(
            f"[CELERY:BACKTEST] [STATUS] Transitioning: {task.status} -> COMPLETED - task_id={task_id}"
        )
        task.status = TaskStatus.COMPLETED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        logger.info(
            f"[CELERY:BACKTEST] [STATUS] Current: COMPLETED - task_id={task_id}, "
            f"completed_at={task.completed_at}"
        )

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

        # Update CeleryTaskStatus to maintain state consistency
        from apps.trading.models.celery import CeleryTaskStatus

        CeleryTaskStatus.objects.filter(
            task_name="trading.tasks.run_backtest_task",
            instance_key=str(task_id),
        ).update(
            status=CeleryTaskStatus.Status.FAILED,
            status_message=f"Task failed: {type(error).__name__}: {error_message}",
        )

        logger.info(f"[CELERY:BACKTEST] CeleryTaskStatus updated to FAILED - task_id={task_id}")

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
        logger.info(f"[STOP:BACKTEST] Stop task started - task_id={task_id}")
        task = BacktestTask.objects.get(pk=task_id)
        logger.info(f"[STOP:BACKTEST] Task loaded - task_id={task_id}, status={task.status}")

        # Handle STOPPING state (normal case)
        if task.status == TaskStatus.STOPPING:
            logger.info(
                f"[STOP:BACKTEST] [STATUS] Current: STOPPING, proceeding with stop - task_id={task_id}"
            )

            # Stop the publisher task first
            logger.info(f"[STOP:BACKTEST] Stopping publisher - task_id={task_id}")
            from apps.market.signals.management import task_management_handler

            task_management_handler.request_market_task_cancel(
                task_name="market.tasks.publish_ticks_for_backtest",
                instance_key=str(task_id),
                reason="Backtest task stopped",
            )
            logger.info(f"[STOP:BACKTEST] Publisher stop signal sent - task_id={task_id}")

            # Wait up to 5 seconds for graceful shutdown
            import time

            logger.info(f"[STOP:BACKTEST] Waiting for graceful shutdown - task_id={task_id}")
            max_wait_seconds = 5
            wait_interval = 0.5
            elapsed = 0

            while elapsed < max_wait_seconds:
                time.sleep(wait_interval)
                elapsed += wait_interval

                # Check if task has stopped
                task.refresh_from_db()
                if task.status == TaskStatus.STOPPED:
                    logger.info(
                        f"[STOP:BACKTEST] Task stopped gracefully - task_id={task_id}, "
                        f"elapsed={elapsed}s"
                    )
                    return

            logger.warning(
                f"[STOP:BACKTEST] Graceful shutdown timeout, forcing termination - task_id={task_id}"
            )

            # Force terminate publisher Celery task
            from celery import current_app

            from apps.trading.models import CeleryTaskStatus

            publisher_celery_status = CeleryTaskStatus.objects.filter(
                task_name="market.tasks.publish_ticks_for_backtest",
                instance_key=str(task_id),
            ).first()

            if publisher_celery_status and publisher_celery_status.celery_task_id:
                logger.info(
                    f"[STOP:BACKTEST] Force revoking publisher Celery task - task_id={task_id}, "
                    f"publisher_celery_task_id={publisher_celery_status.celery_task_id}"
                )
                current_app.control.revoke(
                    publisher_celery_status.celery_task_id, terminate=True, signal="SIGKILL"
                )
                logger.info(
                    f"[STOP:BACKTEST] Publisher Celery task force revoked - task_id={task_id}"
                )
            else:
                logger.warning(
                    f"[STOP:BACKTEST] No publisher Celery task found to revoke - task_id={task_id}"
                )

            # Force termination - Revoke the main Celery task
            if task.celery_task_id:
                logger.info(
                    f"[STOP:BACKTEST] Force revoking main Celery task - task_id={task_id}, "
                    f"celery_task_id={task.celery_task_id}"
                )
                current_app.control.revoke(task.celery_task_id, terminate=True, signal="SIGKILL")
                logger.info(f"[STOP:BACKTEST] Main Celery task force revoked - task_id={task_id}")

            # Update task status to STOPPED (without completed_at since it didn't complete)
            logger.info(
                f"[STOP:BACKTEST] [STATUS] Transitioning: {task.status} -> STOPPED - task_id={task_id}"
            )
            task.refresh_from_db()
            task.status = TaskStatus.STOPPED
            task.completed_at = None
            task.save(update_fields=["status", "completed_at", "updated_at"])
            logger.info(f"[STOP:BACKTEST] [STATUS] Current: STOPPED - task_id={task_id}")

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

        # Handle COMPLETED state (race condition - task completed before stop task ran)
        elif task.status == TaskStatus.COMPLETED:
            logger.warning(
                f"[STOP:BACKTEST] [STATUS] Race condition detected: COMPLETED -> STOPPED - task_id={task_id}"
            )
            # Change from COMPLETED to STOPPED since user requested stop
            task.status = TaskStatus.STOPPED
            task.completed_at = None  # Remove completed_at since it was stopped
            task.save(update_fields=["status", "completed_at", "updated_at"])
            logger.info(f"[STOP:BACKTEST] [STATUS] Current: STOPPED - task_id={task_id}")

        else:
            logger.warning(
                f"[STOP:BACKTEST] [STATUS] Unexpected state: {task.status} - task_id={task_id}"
            )
    except BacktestTask.DoesNotExist:
        logger.error(f"Backtest task {task_id} not found")
        raise
