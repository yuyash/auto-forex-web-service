"""Celery tasks for backtest execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task

from apps.trading.engine import TradingEngine
from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.logging import TaskLoggingSession
from apps.trading.models import BacktestTask
from apps.trading.services.execution_lifecycle import transition_task_to_running
from apps.trading.tasks.lifecycle_events import (
    build_lifecycle_event_spec,
    finalize_task_terminal_lifecycle,
    publish_task_lifecycle_event,
)
from apps.trading.tasks.executor import BacktestExecutor
from apps.trading.tasks.source import RedisTickDataSource
from apps.trading.utils import pip_size_for_instrument

logger: Logger = getLogger(name=__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_backtest_task",
    acks_late=True,
    reject_on_worker_lost=True,
    track_started=True,
)
def run_backtest_task(self: Any, task_id: UUID) -> None:
    """Celery task wrapper for running backtest tasks.

    Args:
        task_id: UUID of the BacktestTask to execute
    """
    task = None
    logging_session: TaskLoggingSession | None = None

    try:
        logger.info(
            f"Task started - task_id={task_id}, "
            f"celery_task_id={self.request.id}, worker={self.request.hostname}"
        )
        task = BacktestTask.objects.get(pk=task_id)
        logging_session = TaskLoggingSession(task)
        logging_session.start()

        logger.info(
            f"Task loaded from DB - task_id={task_id}, "
            f"status={task.status}, instrument={task.instrument}, "
            f"start_time={task.start_time}, end_time={task.end_time}"
        )

        # Guard: only allow execution from STARTING status.
        # This prevents duplicate Celery dispatches or retries from
        # re-running a task that has already completed/failed/stopped.
        if task.status != TaskStatus.STARTING:
            logger.warning(
                f"SKIPPING execution - task_id={task_id}, status={task.status} "
                f"is not STARTING. Another worker may have already processed this task."
            )
            return

        # Atomically transition to RUNNING only if still in STARTING/CREATED.
        # This acts as a distributed lock — only one worker can win.
        rows_updated = transition_task_to_running(task_model=BacktestTask, task_id=task_id)

        if rows_updated == 0:
            # Another worker already transitioned this task
            task.refresh_from_db()
            logger.warning(
                f"SKIPPING execution (lost race) - task_id={task_id}, "
                f"current_status={task.status}. Another worker won the transition."
            )
            return

        task.refresh_from_db()
        logger.info(f"Transitioning: STARTING -> RUNNING - task_id={task_id}")

        logger.info(f"Current: RUNNING - task_id={task_id}, started_at={task.started_at}")

        publish_task_lifecycle_event(
            logger=logger,
            task=task,
            task_type=TaskType.BACKTEST,
            event=build_lifecycle_event_spec(
                kind="task_started",
                description="Backtest task execution started",
                log_level=LogLevel.INFO,
                log_component=__name__,
                log_message="Backtest task execution started",
            ),
        )

        # Execute the backtest
        logger.info(f"Execute backtest - task_id={task_id}")
        execute_backtest(task)
        logger.info(f"Execution completed - task_id={task_id}")

        # Check if task was stopped during execution
        logger.info(f"Checking final status - task_id={task_id}")
        task.refresh_from_db()
        logger.info(f"Current after execution: {task.status} - task_id={task_id}")

        # If task is in STOPPING or STOPPED state, don't mark as completed
        if task.status in [TaskStatus.STOPPED, TaskStatus.STOPPING]:
            logger.info(
                f"Task was stopped during execution, not marking as completed - "
                f"task_id={task_id}, status={task.status}"
            )
            return

        # Mark as completed — atomically transition RUNNING -> COMPLETED.
        # Only allow completion from RUNNING to prevent stale state overwrites.
        logger.info(f"Transitioning: {task.status} -> COMPLETED - task_id={task_id}")
        rows_updated = finalize_task_terminal_lifecycle(
            logger=logger,
            task=task,
            task_type=TaskType.BACKTEST,
            status=TaskStatus.COMPLETED,
            event=build_lifecycle_event_spec(
                kind="task_completed",
                description="Backtest task completed successfully",
                log_level=LogLevel.INFO,
                log_message="Backtest task completed successfully",
                log_component=__name__,
            ),
            expected_current_status=TaskStatus.RUNNING,
        )

        if rows_updated == 0:
            task.refresh_from_db()
            logger.warning(
                f"COMPLETED transition failed - task_id={task_id}, "
                f"current_status={task.status}. Task may have been stopped or failed concurrently."
            )
            return

        logger.info(f"Current: {task.status} - task_id={task_id}, completed_at={task.completed_at}")
        logger.info(
            f"SUCCESS - task_id={task_id}, "
            f"completed_at={task.completed_at}, duration={(task.completed_at - task.started_at).total_seconds()}s"
        )

    except BacktestTask.DoesNotExist:
        logger.error(f"TASK_NOT_FOUND - task_id={task_id}")
        raise
    except Exception as error:
        logger.error(
            f"EXECUTION_FAILED - task_id={task_id}, error={str(error)}",
            exc_info=True,
        )
        handle_exception(task_id, task, error)
        raise
    finally:
        if logging_session:
            logging_session.stop()


def execute_backtest(task: BacktestTask) -> None:
    """Execute a backtest task.

    Args:
        task: Backtest task to execute
    """

    logger.info(
        f"Starting execution - task_id={task.pk}, "
        f"instrument={task.instrument}, pip_size={task.pip_size}"
    )

    # Create trading engine
    logger.info(f"Creating trading engine - task_id={task.pk}")
    # Resolve pip_size: use task value, or derive from instrument
    resolved_pip_size = task.pip_size or pip_size_for_instrument(task.instrument)

    engine = TradingEngine(
        instrument=task.instrument,
        pip_size=resolved_pip_size,
        strategy_config=task.config,
        account_currency=task.account_currency or "USD",
        hedging_enabled=task.hedging_enabled,
    )

    # Persist pip_size back to task if it was null
    if not task.pip_size:
        task.pip_size = resolved_pip_size
        task.save(update_fields=["pip_size", "updated_at"])

    # Create data source - use task.pk as request_id to match publisher
    request_id = str(task.pk)
    channel = f"market:backtest:ticks:{request_id}"
    logger.info(
        f"Creating data source - task_id={task.pk}, channel={channel}, request_id={request_id}"
    )
    data_source = RedisTickDataSource(
        channel=channel,
        batch_size=100,
        trigger_publisher=lambda: trigger_backtest_publisher(task),
    )

    logger.info(f"Creating executor - task_id={task.pk}")
    executor = BacktestExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
    )

    # Execute
    logger.info(f"Starting executor.execute() - task_id={task.pk}")
    executor.execute()
    logger.info(f"Executor completed - task_id={task.pk}")


def handle_exception(task_id: UUID, task: BacktestTask | None, error: Exception) -> None:
    # Capture error details and update task
    error_message = str(error)
    error_traceback = traceback.format_exc()

    logger.error(
        f"EXCEPTION_HANDLER - task_id={task_id}, "
        f"error_type={type(error).__name__}, error={error_message}",
        exc_info=True,
    )

    if task:
        # Update task with error information
        finalize_task_terminal_lifecycle(
            logger=logger,
            task=task,
            task_type=TaskType.BACKTEST,
            status=TaskStatus.FAILED,
            event=build_lifecycle_event_spec(
                kind="task_failed",
                description=f"Backtest task failed: {type(error).__name__}: {error_message}",
                log_level=LogLevel.ERROR,
                log_message=(
                    f"Backtest task execution failed: {type(error).__name__}: {error_message}"
                ),
                log_component=__name__,
            ),
            error_message=error_message,
            error_traceback=error_traceback,
        )

        logger.info(f"Task marked as FAILED - task_id={task_id}, completed_at={task.completed_at}")


def trigger_backtest_publisher(task: BacktestTask) -> None:
    """Trigger the backtest data publisher.

    Args:
        task: Backtest task
    """
    from apps.market.tasks import publish_ticks_for_backtest

    # Use task.pk as the request_id to match the channel
    request_id = str(task.pk)

    logger.info(
        f"Triggering backtest publisher - task_id={task.pk}, "
        f"request_id={request_id}, instrument={task.instrument}, "
        f"start={task.start_time}, end={task.end_time}"
    )

    # Check if market worker is available
    from celery import current_app

    inspect = current_app.control.inspect(timeout=3.0)
    active_queues = inspect.active_queues() or {}

    backtest_workers: list[str] = []
    worker_queue_map: dict[str, list[str]] = {}
    for worker, queues in active_queues.items():
        queue_names: list[str] = []
        for queue_info in queues or []:
            if not isinstance(queue_info, dict):
                continue
            queue_name = str(queue_info.get("name", "")).strip()
            if not queue_name:
                continue
            queue_names.append(queue_name)
        worker_queue_map[str(worker)] = queue_names
        if "backtest" in queue_names:
            backtest_workers.append(str(worker))

    if not backtest_workers:
        queue_diag = (
            ", ".join(
                f"{worker}=[{','.join(queue_names) or '-'}]"
                for worker, queue_names in sorted(worker_queue_map.items())
            )
            or "none"
        )
        # Do not fail hard here: inspect can be temporarily unavailable even while
        # workers are alive. We still submit publisher task and let normal timeout/
        # task-level error handling decide failure if it truly cannot run.
        logger.warning(
            "NO_BACKTEST_WORKER_DETECTED - proceeding to submit publisher task anyway "
            "- task_id=%s, active_workers=%s",
            task.pk,
            queue_diag,
        )
    else:
        logger.info(
            "Backtest worker found - workers=%s, task_id=%s",
            ",".join(backtest_workers),
            task.pk,
        )
    # Trigger async task to the backtest queue explicitly.
    result = publish_ticks_for_backtest.apply_async(
        kwargs={
            "instrument": task.instrument,
            "start": task.start_time.isoformat(),
            "end": task.end_time.isoformat(),
            "request_id": request_id,
        },
        queue="backtest",
    )
    logger.info(
        f"Publisher task submitted - task_id={task.pk}, "
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
                f"[STOP:BACKTEST] Current: STOPPING, proceeding with stop - task_id={task_id}"
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

            from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus

            publisher_celery_status = MarketCeleryTaskStatus.objects.filter(
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
            if task.execution_id:
                logger.info(
                    f"[STOP:BACKTEST] Force revoking main Celery task - task_id={task_id}, "
                    f"execution_id={task.execution_id}"
                )
                current_app.control.revoke(str(task.execution_id), terminate=True, signal="SIGKILL")
                logger.info(f"[STOP:BACKTEST] Main Celery task force revoked - task_id={task_id}")

            # Update task status to STOPPED (without completed_at since it didn't complete)
            logger.info(
                f"[STOP:BACKTEST] Transitioning: {task.status} -> STOPPED - task_id={task_id}"
            )
            finalize_task_terminal_lifecycle(
                logger=logger,
                task=task,
                task_type=TaskType.BACKTEST,
                status=TaskStatus.STOPPED,
                event=build_lifecycle_event_spec(
                    kind="task_stopped",
                    description="Backtest task stopped",
                    log_level=LogLevel.INFO,
                    log_message="Backtest task stopped",
                    log_component=__name__,
                ),
                expected_current_status=TaskStatus.STOPPING,
                extra_details={"mode": "worker_stop"},
            )
            logger.info(f"[STOP:BACKTEST] Current: STOPPED - task_id={task_id}")

            logger.info(f"Backtest task {task_id} stopped successfully")

        # Handle COMPLETED state (race condition - task completed before stop task ran)
        elif task.status == TaskStatus.COMPLETED:
            logger.warning(
                f"[STOP:BACKTEST] Race condition detected: COMPLETED -> STOPPED - task_id={task_id}"
            )
            # Change from COMPLETED to STOPPED since user requested stop
            finalize_task_terminal_lifecycle(
                logger=logger,
                task=task,
                task_type=TaskType.BACKTEST,
                status=TaskStatus.STOPPED,
                event=build_lifecycle_event_spec(
                    kind="task_stopped",
                    description="Backtest task stopped after completion race",
                    log_level=LogLevel.INFO,
                    log_message="Backtest task stopped after completion race",
                    log_component=__name__,
                ),
                expected_current_status=TaskStatus.COMPLETED,
                extra_details={"mode": "worker_stop"},
            )
            logger.info(f"[STOP:BACKTEST] Current: STOPPED - task_id={task_id}")

        else:
            logger.warning(f"[STOP:BACKTEST] Unexpected state: {task.status} - task_id={task_id}")
    except BacktestTask.DoesNotExist:
        logger.error(f"Backtest task {task_id} not found")
        raise
