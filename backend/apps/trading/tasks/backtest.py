"""Celery tasks for backtest execution."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from celery import shared_task

from django.utils import timezone as dj_timezone

from apps.trading.engine import TradingEngine
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.logging import TaskLoggingSession
from apps.trading.models import BacktestTask
from apps.trading.services.execution_lifecycle import transition_task_to_running
from apps.trading.tasks.executor import BacktestExecutor
from apps.trading.tasks.lifecycle_events import (
    build_completed_event_spec,
    build_started_event_spec,
    build_stopped_event_spec,
    finalize_task_terminal_lifecycle,
    publish_task_lifecycle_event,
)
from apps.trading.tasks.source import RedisStreamTickDataSource
from apps.trading.tasks.task_runner import handle_task_exception
from apps.trading.utils import pip_size_for_instrument

logger = logging.getLogger(__name__)


def _stop_previous_publisher(request_id: str) -> None:
    """Request any running publisher for *request_id* to stop and wait briefly.

    The publisher polls CeleryTaskStatus for a STOPPING flag.  Setting it
    causes the publisher to exit on its next stop-check iteration.
    We then wait up to 5 s for it to actually terminate.
    """
    import time

    from apps.market.models.celery import CeleryTaskStatus

    task_name = "market.tasks.publish_ticks_for_backtest"
    rows = CeleryTaskStatus.objects.filter(
        task_name=task_name,
        instance_key=request_id,
        status=CeleryTaskStatus.Status.RUNNING,
    ).update(status=CeleryTaskStatus.Status.STOPPING)

    if not rows:
        return

    logger.info("Requested previous publisher to stop - request_id=%s", request_id)

    for _ in range(10):
        still_running = CeleryTaskStatus.objects.filter(
            task_name=task_name,
            instance_key=request_id,
            status__in=(CeleryTaskStatus.Status.RUNNING, CeleryTaskStatus.Status.STOPPING),
        ).exists()
        if not still_running:
            break
        time.sleep(0.5)


def _purge_stale_task_streams(request_id: str, *, keep_execution_id: str | None = None) -> None:
    """Delete leftover backtest stream keys for this task.

    The stream key format is ``market:backtest:stream:<task_id>[:<execution_id>]``.
    Old runs — including legacy runs that used the task-id-only key before
    execution-id scoping was introduced — can leave Redis Stream entries
    behind that would otherwise be delivered to a new subscriber and make
    simulated time appear to jump.  This sweeps any key matching the
    task-id prefix except the one we are about to use.
    """
    from apps.market.tasks.base import backtest_stream_key_for_request
    from apps.market.tasks.base import redis_client

    prefix_only = backtest_stream_key_for_request(request_id)
    keep_key = (
        backtest_stream_key_for_request(request_id, keep_execution_id)
        if keep_execution_id
        else prefix_only
    )
    pattern = f"{prefix_only}*"

    try:
        client = redis_client()
    except Exception as exc:  # nosec B110
        logger.debug(
            "Could not open Redis client for stream purge - request_id=%s, error=%s",
            request_id,
            exc,
        )
        return

    deleted: list[str] = []
    try:
        for key in client.scan_iter(match=pattern, count=100):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if key_str == keep_key:
                continue
            try:
                client.delete(key)
                deleted.append(key_str)
            except Exception as exc:  # nosec B110
                logger.debug(
                    "Stream DEL failed (non-fatal) - request_id=%s, key=%s, error=%s",
                    request_id,
                    key_str,
                    exc,
                )
    except Exception as exc:  # nosec B110
        logger.debug(
            "Stream SCAN failed (non-fatal) - request_id=%s, pattern=%s, error=%s",
            request_id,
            pattern,
            exc,
        )
        return

    if deleted:
        logger.info(
            "Purged %d stale backtest stream key(s) - request_id=%s, keys=%s",
            len(deleted),
            request_id,
            deleted,
        )


@shared_task(
    bind=True,
    name="trading.tasks.run_backtest_task",
    acks_late=True,
    reject_on_worker_lost=True,
    track_started=True,
)
def run_backtest_task(self: Any, task_id: UUID) -> None:
    """Celery task wrapper for running backtest tasks."""
    task = None
    logging_session: TaskLoggingSession | None = None

    try:
        logger.info(
            "Task started - task_id=%s, celery_task_id=%s, worker=%s",
            task_id,
            self.request.id,
            self.request.hostname,
        )
        task = BacktestTask.objects.get(pk=task_id)
        logging_session = TaskLoggingSession(task)
        logging_session.start()

        logger.info(
            "Task loaded from DB - task_id=%s, status=%s, instrument=%s, "
            "start_time=%s, end_time=%s",
            task_id,
            task.status,
            task.instrument,
            task.start_time,
            task.end_time,
        )

        # Guard: only allow execution from STARTING status.
        if task.status != TaskStatus.STARTING:
            logger.warning(
                "SKIPPING execution - task_id=%s, status=%s is not STARTING",
                task_id,
                task.status,
            )
            return

        # Atomically transition to RUNNING — distributed lock.
        rows_updated = transition_task_to_running(task_model=BacktestTask, task_id=task_id)
        if rows_updated == 0:
            task.refresh_from_db()
            logger.warning(
                "SKIPPING execution (lost race) - task_id=%s, current_status=%s",
                task_id,
                task.status,
            )
            return

        task.refresh_from_db()
        logger.info("Transitioning: STARTING -> RUNNING - task_id=%s", task_id)

        publish_task_lifecycle_event(
            logger=logger,
            task=task,
            task_type=TaskType.BACKTEST,
            event=build_started_event_spec(task_label="Backtest", component=__name__),
        )

        execute_backtest(task)

        # Check if task was stopped during execution
        task.refresh_from_db()
        if task.status in [TaskStatus.STOPPED, TaskStatus.STOPPING, TaskStatus.PAUSED]:
            logger.info(
                "Task execution interrupted - task_id=%s, status=%s",
                task_id,
                task.status,
            )
            return

        # Mark as completed
        rows_updated = finalize_task_terminal_lifecycle(
            logger=logger,
            task=task,
            task_type=TaskType.BACKTEST,
            status=TaskStatus.COMPLETED,
            event=build_completed_event_spec(task_label="Backtest", component=__name__),
            expected_current_status=TaskStatus.RUNNING,
        )
        if rows_updated == 0:
            task.refresh_from_db()
            if task.status == TaskStatus.FAILED:
                # The data publisher may have marked the task FAILED due to
                # insufficient tick data coverage while the executor was
                # still processing.  The execution itself completed
                # successfully, so override to COMPLETED and preserve the
                # data-gap warning in error_message.
                logger.info(
                    "Overriding FAILED → COMPLETED (execution succeeded) - task_id=%s, "
                    "prior_error=%s",
                    task_id,
                    task.error_message,
                )
                task.status = TaskStatus.COMPLETED
                task.completed_at = dj_timezone.now()
                task.save(update_fields=["status", "completed_at", "updated_at"])
            else:
                logger.warning(
                    "COMPLETED transition failed - task_id=%s, current_status=%s",
                    task_id,
                    task.status,
                )
                return

        logger.info(
            "SUCCESS - task_id=%s, completed_at=%s",
            task_id,
            task.completed_at,
        )

    except BacktestTask.DoesNotExist:
        logger.error("TASK_NOT_FOUND - task_id=%s", task_id)
        raise
    except Exception as error:
        logger.error("EXECUTION_FAILED - task_id=%s, error=%s", task_id, error, exc_info=True)
        handle_task_exception(
            task_id=task_id,
            task=task,
            error=error,
            task_type=TaskType.BACKTEST,
            task_label="Backtest",
            component=__name__,
        )
        raise
    finally:
        if logging_session:
            logging_session.stop()


def execute_backtest(task: BacktestTask) -> None:
    """Execute a backtest task."""
    logger.info(
        "Starting execution - task_id=%s, instrument=%s, pip_size=%s",
        task.pk,
        task.instrument,
        task.pip_size,
    )

    resolved_pip_size = task.pip_size or pip_size_for_instrument(task.instrument)

    engine = TradingEngine(
        instrument=task.instrument,
        pip_size=resolved_pip_size,
        strategy_config=task.config,
        account_currency=task.account_currency or "USD",
        hedging_enabled=task.hedging_enabled,
    )

    if not task.pip_size:
        task.pip_size = resolved_pip_size
        task.save(update_fields=["pip_size", "updated_at"])

    request_id = str(task.pk)
    # Backtest ticks are delivered over a Redis Stream (not Pub/Sub) so that
    # slow-consumer situations translate into backpressure on the publisher
    # rather than silent message loss.  The stream key is scoped to the
    # current execution id so a restarted task never inherits leftover
    # entries from an older execution — one of the failure modes we've seen
    # in production is a new run reading stale ticks from the previous run
    # and jumping forward in simulated time.
    from apps.market.tasks.base import backtest_stream_key_for_request

    execution_id_for_stream = (
        str(task.execution_id) if getattr(task, "execution_id", None) else None
    )
    stream_key = backtest_stream_key_for_request(request_id, execution_id_for_stream)

    # Stop any previous publisher and wipe any leftover Redis state from a
    # prior execution of this task.  Backtest restarts always begin from
    # ``task.start_time`` so there is nothing to preserve; carrying
    # leftover entries over is how we previously saw simulated time jump
    # across a 237-day gap in production.
    _stop_previous_publisher(request_id)
    _purge_stale_task_streams(request_id, keep_execution_id=execution_id_for_stream)

    data_source = RedisStreamTickDataSource(
        stream_key=stream_key,
        batch_size=100,
        trigger_publisher=lambda: trigger_backtest_publisher(task),
    )

    executor = BacktestExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
    )
    executor.execute()


def trigger_backtest_publisher(
    task: BacktestTask,
) -> None:
    """Trigger the backtest data publisher.

    Backtests always replay from ``task.start_time``.  Earlier revisions
    supported a ``resume_from`` optimisation that rewound the publisher to
    the last processed tick timestamp when resuming, but in practice a
    backtest restart always allocates a fresh ``execution_id`` (see
    ``TaskService.start_task``) so there is nothing to resume.  The
    optimisation also interacted badly with the per-task Redis Stream
    (pre-fix) because a subscriber could see stale entries from a prior
    execution and jump forward in simulated time.

    Args:
        task: The backtest task.
    """
    from apps.market.tasks import publish_ticks_for_backtest

    request_id = str(task.pk)

    effective_start = task.start_time

    logger.info(
        "Triggering backtest publisher - task_id=%s, request_id=%s, "
        "instrument=%s, start=%s, end=%s, tick_granularity=%s, tick_window_value_mode=%s",
        task.pk,
        request_id,
        task.instrument,
        effective_start,
        task.end_time,
        task.tick_granularity,
        task.tick_window_value_mode,
    )

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

    execution_id = getattr(task, "execution_id", None)
    result = publish_ticks_for_backtest.apply_async(
        kwargs={
            "instrument": task.instrument,
            "start": effective_start.isoformat(),
            "end": task.end_time.isoformat(),
            "request_id": request_id,
            "tick_granularity": task.tick_granularity,
            "tick_window_value_mode": task.tick_window_value_mode,
            "execution_id": str(execution_id) if execution_id else None,
        },
        queue="backtest_publisher",
    )
    logger.info(
        "Publisher task submitted - task_id=%s, execution_id=%s, "
        "publisher_celery_task_id=%s, channel=%s",
        task.pk,
        execution_id,
        result.id,
        f"market:backtest:stream:{request_id}:{execution_id}"
        if execution_id
        else f"market:backtest:stream:{request_id}",
    )


@shared_task(bind=True, name="trading.tasks.stop_backtest_task")
def stop_backtest_task(self: Any, task_id: UUID) -> None:
    """Stop a running backtest task."""
    from apps.trading.enums import TaskStatus

    try:
        logger.info("[STOP:BACKTEST] Stop task started - task_id=%s", task_id)
        task = BacktestTask.objects.get(pk=task_id)
        logger.info("[STOP:BACKTEST] Task loaded - task_id=%s, status=%s", task_id, task.status)

        if task.status == TaskStatus.STOPPING:
            logger.info("[STOP:BACKTEST] Current: STOPPING, proceeding - task_id=%s", task_id)

            from apps.market.signals.management import task_management_handler

            task_management_handler.request_market_task_cancel(
                task_name="market.tasks.publish_ticks_for_backtest",
                instance_key=str(task_id),
                reason="Backtest task stopped",
            )

            import time

            max_wait_seconds = 5
            wait_interval = 0.5
            elapsed = 0.0

            while elapsed < max_wait_seconds:
                time.sleep(wait_interval)
                elapsed += wait_interval
                task.refresh_from_db()
                if task.status == TaskStatus.STOPPED:
                    logger.info(
                        "[STOP:BACKTEST] Task stopped gracefully - task_id=%s, elapsed=%.1fs",
                        task_id,
                        elapsed,
                    )
                    return

            logger.warning(
                "[STOP:BACKTEST] Graceful shutdown timeout, forcing - task_id=%s", task_id
            )

            from celery import current_app

            from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus

            publisher_celery_status = MarketCeleryTaskStatus.objects.filter(
                task_name="market.tasks.publish_ticks_for_backtest",
                instance_key=str(task_id),
            ).first()

            if publisher_celery_status and publisher_celery_status.celery_task_id:
                current_app.control.revoke(
                    publisher_celery_status.celery_task_id, terminate=True, signal="SIGKILL"
                )

            if task.execution_id:
                current_app.control.revoke(str(task.execution_id), terminate=True, signal="SIGKILL")

            finalize_task_terminal_lifecycle(
                logger=logger,
                task=task,
                task_type=TaskType.BACKTEST,
                status=TaskStatus.STOPPED,
                event=build_stopped_event_spec(
                    task_label="Backtest",
                    component=__name__,
                    description="Backtest task stopped",
                ),
                expected_current_status=TaskStatus.STOPPING,
                extra_details={"mode": "worker_stop"},
            )

        elif task.status == TaskStatus.COMPLETED:
            logger.warning("[STOP:BACKTEST] Race: COMPLETED -> STOPPED - task_id=%s", task_id)
            finalize_task_terminal_lifecycle(
                logger=logger,
                task=task,
                task_type=TaskType.BACKTEST,
                status=TaskStatus.STOPPED,
                event=build_stopped_event_spec(
                    task_label="Backtest",
                    component=__name__,
                    description="Backtest task stopped after completion race",
                ),
                expected_current_status=TaskStatus.COMPLETED,
                extra_details={"mode": "worker_stop"},
            )

        else:
            logger.warning(
                "[STOP:BACKTEST] Unexpected state: %s - task_id=%s", task.status, task_id
            )
    except BacktestTask.DoesNotExist:
        logger.error("Backtest task %s not found", task_id)
        raise
