"""Command objects for task lifecycle orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from logging import Logger
from typing import TYPE_CHECKING, Callable
from uuid import UUID, uuid4

from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction

from apps.trading.enums import StopMode, TaskStatus
from apps.trading.models import BacktestTask, TradingTask
from apps.trading.tasks.lifecycle_events import TaskLifecycleEventPublisher
from apps.trading.tasks.lifecycle_state_machine import allowed_statuses_for_command

if TYPE_CHECKING:
    from apps.trading.tasks.service import TaskService


@dataclass(frozen=True)
class LifecycleCommandAdapters:
    """External side effects used by lifecycle commands."""

    inspect_workers: Callable[[], dict[str, object] | None]
    signal_stop: Callable[[UUID, str, object], None]
    signal_pause: Callable[[UUID, str, object], None]
    revoke_execution: Callable[[object], None]
    dispatch_stop: Callable[[UUID, bool, StopMode], None]
    sleep: Callable[[float], None]


def _default_inspect_workers() -> dict[str, object] | None:
    from celery import current_app

    return current_app.control.inspect(timeout=3.0).active()


def _default_signal_stop(task_id: UUID, task_name: str, execution_id: object) -> None:
    import redis
    from django.conf import settings

    redis_client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
    redis_instance_key = f"{task_id}:{execution_id}"
    redis_key = f"task:coord:{task_name}:{redis_instance_key}"
    redis_client.hset(redis_key, "status", "stopping")
    redis_client.expire(redis_key, 3600)
    redis_client.close()


def _default_signal_pause(task_id: UUID, task_name: str, execution_id: object) -> None:
    import redis
    from django.conf import settings

    redis_client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
    redis_instance_key = f"{task_id}:{execution_id}"
    redis_key = f"task:coord:{task_name}:{redis_instance_key}"
    redis_client.hset(redis_key, "status", "pausing")
    redis_client.expire(redis_key, 3600)
    redis_client.close()


def _default_revoke_execution(celery_task_id: object) -> None:
    from celery import current_app

    current_app.control.revoke(str(celery_task_id), terminate=True, signal="SIGKILL")


def _default_dispatch_stop(task_id: UUID, is_backtest: bool, stop_mode: StopMode) -> None:
    from apps.trading.tasks import service as service_module

    if is_backtest:
        service_module.stop_backtest_task.apply_async(
            args=[task_id, stop_mode.value],
            queue="system",
        )
    else:
        service_module.stop_trading_task.apply_async(
            args=[task_id, stop_mode.value],
            queue="system",
        )


class TaskLifecycleCommands:
    """Encapsulate task lifecycle command flows behind explicit operations."""

    def __init__(
        self,
        *,
        service: TaskService,
        logger: Logger,
        events: TaskLifecycleEventPublisher | None = None,
        adapters: LifecycleCommandAdapters | None = None,
    ) -> None:
        self.service = service
        self.logger = logger
        self.events = events or TaskLifecycleEventPublisher(logger=logger)
        self.adapters = adapters or LifecycleCommandAdapters(
            inspect_workers=_default_inspect_workers,
            signal_stop=_default_signal_stop,
            signal_pause=_default_signal_pause,
            revoke_execution=_default_revoke_execution,
            dispatch_stop=_default_dispatch_stop,
            sleep=time.sleep,
        )

    def start(self, task: BacktestTask | TradingTask) -> BacktestTask | TradingTask:
        self._assert_transition_allowed(
            command="start",
            task_status=task.status,
            message=(f"Task must be in CREATED status to submit (current status: {task.status})"),
        )
        self.logger.info(
            "[SERVICE:START] Submitting task - task_id=%s, task_status=%s, instrument=%s, start_time=%s, end_time=%s",
            task.pk,
            task.status,
            task.instrument,
            getattr(task, "start_time", "N/A"),
            getattr(task, "end_time", "N/A"),
        )

        is_backtest_task = isinstance(task, BacktestTask) or hasattr(task, "start_time")
        model_class = BacktestTask if is_backtest_task else TradingTask
        task_type = "backtest" if is_backtest_task else "trading"

        try:
            task = self._prepare_start(task=task, model_class=model_class)
            self.logger.info(
                "[SERVICE:START] Task type determined - task_id=%s, type=%s, execution_id=%s",
                task.pk,
                task_type,
                task.execution_id,
            )
            self.logger.info(
                "[SERVICE:START] Submitting to Celery - task_id=%s, execution_id=%s",
                task.pk,
                task.execution_id,
            )
            self.service._dispatch_task(task, task_type)
            if task_type == "trading":
                self._kick_market_supervisor()
            self.logger.info(
                "[SERVICE:START] Task submitted to Celery - task_id=%s, execution_id=%s, new_status=%s",
                task.pk,
                task.execution_id,
                task.status,
            )
            self._audit_lifecycle_transition(
                command="start",
                task_id=task.pk,
                task_type=task_type,
                from_status=TaskStatus.CREATED,
                to_status=task.status,
                execution_id=task.execution_id,
                celery_task_id=getattr(task, "celery_task_id", None),
            )
            self.events.publish(
                task=task,
                task_type=task_type,
                kind="task_start_requested",
                description="Task start requested",
            )
            self._log_worker_state(task)
            return task
        except Exception:
            self._reset_failed_start(task=task, model_class=model_class)
            raise

    def _kick_market_supervisor(self) -> None:
        """Kick the market tick supervisor outside eager test execution."""
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            self.logger.info("[SERVICE:START] Skipping market supervisor kick in eager Celery mode")
            return

        from apps.market.tasks import ensure_tick_pubsub_running

        ensure_tick_pubsub_running.apply_async(countdown=0, queue="system")

    def stop(
        self,
        task_id: UUID,
        mode: str = "graceful",
        *,
        drain_duration_minutes: int | None = None,
    ) -> bool:
        self.logger.info(
            "[SERVICE:STOP] Stopping task - task_id=%s, mode=%s, drain_duration_minutes=%s",
            task_id,
            mode,
            drain_duration_minutes,
        )
        try:
            stop_mode = StopMode(mode)
        except ValueError as exc:
            raise ValueError(f"Invalid stop mode: {mode}") from exc
        task, task_type = self.service._get_task_and_type(task_id)
        is_backtest = task_type == "backtest"
        task_name = (
            "trading.tasks.run_backtest_task" if is_backtest else "trading.tasks.run_trading_task"
        )

        self.logger.info(
            "[SERVICE:STOP] Current task state - task_id=%s, status=%s, execution_id=%s",
            task_id,
            task.status,
            task.execution_id,
        )
        previous_status = task.status

        if task.status in [TaskStatus.STOPPED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.logger.info(
                "[SERVICE:STOP] Already in terminal state: %s - task_id=%s",
                task.status,
                task_id,
            )
            return True
        self._assert_transition_allowed(
            command="stop",
            task_status=task.status,
            message=f"Task cannot be stopped from {task.status} state",
        )

        # A stop issued while the task is DRAINING means the user wants to
        # terminate now rather than waiting for positions to reach breakeven.
        # Promote the stop mode to IMMEDIATE so the Celery worker is
        # revoked and the task transitions straight to STOPPED.
        if task.status == TaskStatus.DRAINING and stop_mode == StopMode.DRAIN:
            stop_mode = StopMode.IMMEDIATE
            self.logger.info(
                "[SERVICE:STOP] DRAINING task received another drain stop, "
                "escalating to IMMEDIATE - task_id=%s",
                task_id,
            )
        elif task.status == TaskStatus.DRAINING and stop_mode == StopMode.GRACEFUL:
            # Same idea: draining is already a "graceful wait" — a plain
            # stop while draining means "stop now, don't keep waiting".
            stop_mode = StopMode.IMMEDIATE
            self.logger.info(
                "[SERVICE:STOP] DRAINING task received graceful stop, "
                "escalating to IMMEDIATE - task_id=%s",
                task_id,
            )

        # DRAIN mode parks the task in DRAINING while it gradually closes
        # positions at break-even.  Only live trading tasks support it; for
        # backtests we treat it the same as GRACEFUL_CLOSE (the executor
        # finishes on end-of-data anyway).
        if stop_mode == StopMode.DRAIN and not is_backtest:
            next_status: TaskStatus = TaskStatus.DRAINING
        elif stop_mode == StopMode.DRAIN and is_backtest:
            next_status = TaskStatus.DRAINING
        else:
            next_status = TaskStatus.STOPPING

        task.status = next_status
        update_fields = ["status", "updated_at"]
        # Both trading and backtest tasks persist the ``sell_on_stop`` flag
        # so the worker that runs the shutdown logic can close open
        # positions at current market / tick prices.
        if stop_mode == StopMode.GRACEFUL_CLOSE:
            task.sell_on_stop = True
            update_fields.append("sell_on_stop")
        task.save(update_fields=update_fields)
        self._audit_lifecycle_transition(
            command="stop",
            task_id=task.pk,
            task_type=task_type,
            from_status=previous_status,
            to_status=task.status,
            execution_id=task.execution_id,
            celery_task_id=getattr(task, "celery_task_id", None),
            mode=stop_mode.value,
            drain_duration_minutes=drain_duration_minutes,
        )

        # Persist per-stop drain duration override so the executor picks
        # it up on the next drain evaluation. Written only when drain is
        # the effective mode and a positive value was supplied.
        if stop_mode == StopMode.DRAIN and drain_duration_minutes and drain_duration_minutes > 0:
            self._record_drain_duration_minutes_override(
                task_id=task_id,
                task_type=task_type,
                execution_id=task.execution_id,
                minutes=int(drain_duration_minutes),
            )

        self._signal_redis_stop(
            task_id=task_id, task_name=task_name, execution_id=task.execution_id
        )
        # Fall back to execution_id for older rows that pre-date the
        # celery_task_id field and may still have it set to NULL.
        celery_id = getattr(task, "celery_task_id", None) or task.execution_id
        if stop_mode == StopMode.IMMEDIATE and celery_id:
            self._revoke_execution(celery_id)
        # DRAIN mode keeps the worker running — don't dispatch the stop
        # finalisation task; the executor will transition to STOPPED when
        # it finishes draining.
        if stop_mode != StopMode.DRAIN:
            self._trigger_stop_task(task_id=task_id, is_backtest=is_backtest, stop_mode=stop_mode)

        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_drain_requested" if stop_mode == StopMode.DRAIN else "task_stop_requested",
            description=(
                "Task drain requested" if stop_mode == StopMode.DRAIN else "Task stop requested"
            ),
            extra_details={"mode": stop_mode.value},
        )
        return True

    def pause(self, task_id: UUID) -> bool:
        task, task_type = self.service._get_task_and_type(task_id)
        previous_status = task.status

        # Pause is only supported for backtest tasks.  Trading tasks should
        # use stop (which preserves execution state) and then resume.
        if task_type == "trading":
            raise ValueError(
                "Pause is not supported for trading tasks. "
                "Use stop instead — stopped trading tasks can be resumed."
            )

        self._assert_transition_allowed(
            command="pause",
            task_status=task.status,
            message=(
                f"Task cannot be paused in {task.status} state. "
                "Only STARTING or RUNNING tasks can be paused."
            ),
        )
        task_name = (
            "trading.tasks.run_backtest_task"
            if task_type == "backtest"
            else "trading.tasks.run_trading_task"
        )
        self.service.writer.persist_state(task, status=TaskStatus.PAUSED)
        self._audit_lifecycle_transition(
            command="pause",
            task_id=task.pk,
            task_type=task_type,
            from_status=previous_status,
            to_status=TaskStatus.PAUSED,
            execution_id=task.execution_id,
            celery_task_id=getattr(task, "celery_task_id", None),
        )
        self._signal_redis_pause(
            task_id=task_id,
            task_name=task_name,
            execution_id=task.execution_id,
        )
        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_pause_requested",
            description="Task pause requested",
        )
        return True

    def cancel(self, task_id: UUID) -> bool:
        task, task_type = self.service._get_task_and_type(task_id)
        if task.status not in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.PAUSED]:
            self.logger.warning(
                "Task not in cancellable state",
                extra={"task_id": str(task_id), "status": task.status},
            )
            return False

        # Fall back to execution_id for older rows that pre-date the
        # celery_task_id field.
        celery_id = getattr(task, "celery_task_id", None) or task.execution_id
        result = self.service.get_celery_result(str(celery_id) if celery_id else None)
        if result:
            result.revoke(terminate=True)

        self.service._finalize_terminal_task(
            task=task,
            task_type=task_type,
            status=TaskStatus.STOPPED,
            description="Task cancelled",
            kind="task_cancelled",
        )
        return True

    def restart(self, task_id: UUID) -> BacktestTask | TradingTask:
        task, task_type = self.service._get_task_and_type(task_id)
        self._assert_transition_allowed(
            command="restart",
            task_status=task.status,
            message=f"Task cannot be restarted from {task.status} state",
        )
        previous_status = task.status
        if task.status in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]:
            try:
                self.service.stop_task(task_id)
                self.adapters.sleep(1)
                task.refresh_from_db()
            except Exception as exc:  # pragma: no cover - defensive logging path
                self.logger.warning(
                    "[SERVICE:RESTART] Stop failed, forcing restart anyway - task_id=%s, error=%s",
                    task_id,
                    exc,
                )

        # Fall back to execution_id for older rows that pre-date the
        # celery_task_id field.
        celery_id = getattr(task, "celery_task_id", None) or task.execution_id
        if celery_id:
            self._revoke_execution(celery_id)

        self.service.writer.clear_execution_history(task=task, task_type=task_type)
        type(task).objects.filter(pk=task.pk).update(
            execution_id=None,
            celery_task_id=None,
            status=TaskStatus.CREATED,
            started_at=None,
            completed_at=None,
            error_message=None,
            error_traceback=None,
        )
        task.refresh_from_db()
        if task.status != TaskStatus.CREATED:
            raise RuntimeError(f"Failed to reset task status: expected CREATED, got {task.status}")
        self._audit_lifecycle_transition(
            command="restart",
            task_id=task.pk,
            task_type=task_type,
            from_status=previous_status,
            to_status=TaskStatus.CREATED,
            execution_id=task.execution_id,
            celery_task_id=getattr(task, "celery_task_id", None),
        )
        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_restart_requested",
            description="Task restart requested",
        )
        return self.service.start_task(task)

    def resume(self, task_id: UUID) -> BacktestTask | TradingTask:
        task, task_type = self.service._get_task_and_type(task_id)
        model_class = self.service._get_task_model(task_type)
        is_trading = task_type == "trading"

        # Trading tasks can resume from PAUSED, STOPPED, or FAILED.
        # Backtests can resume from PAUSED or STOPPED while preserving their
        # execution_id and ExecutionState; the publisher continues from the
        # last processed tick instead of replaying from task.start_time.
        if is_trading:
            allowed_statuses = allowed_statuses_for_command("resume_trading")
        else:
            allowed_statuses = allowed_statuses_for_command("resume_backtest")

        with transaction.atomic():
            locked_task = model_class.objects.select_for_update().get(pk=task.pk)
            previous_status = locked_task.status
            self._assert_transition_allowed(
                command="resume_trading" if is_trading else "resume_backtest",
                task_status=locked_task.status,
                message=(
                    f"Task cannot be resumed from {locked_task.status} state. "
                    f"Only {', '.join(str(s.value).upper() for s in allowed_statuses)} tasks can be resumed."
                ),
            )
            if not locked_task.execution_id:
                from apps.trading.tasks.service import TaskValidationError

                raise TaskValidationError("Cannot resume task without an execution_id")

            try:
                from apps.trading.services.resume_config import (
                    log_effective_resume_configuration,
                    validate_resume_configuration,
                )

                audit = validate_resume_configuration(task=locked_task, task_type=task_type)
                log_effective_resume_configuration(
                    logger=self.logger,
                    audit=audit,
                    task=locked_task,
                )
            except ValueError as exc:
                from apps.trading.tasks.service import TaskValidationError

                raise TaskValidationError(str(exc)) from exc

            previous_celery_task_id = locked_task.celery_task_id
            result = self.service.get_celery_result(
                str(previous_celery_task_id) if previous_celery_task_id else None
            )
            self._ensure_resumeable_celery_state(
                result=result,
                task_id=task_id,
                db_status=locked_task.status,
                celery_task_id=previous_celery_task_id,
            )

            # Revoke any lingering Celery task for this execution before
            # dispatching a new one. This is a no-op for a clean exit but
            # defensively handles cases where a previous worker crashed
            # without cleaning up its result backend entry.
            #
            # After revoking, we MUST allocate a fresh ``celery_task_id``
            # for the next run: Celery's revoke list persists by task_id,
            # so re-submitting ``apply_async(task_id=<same>)`` causes the
            # worker to drop the message immediately (the symptom is a
            # task stuck in STARTING indefinitely).  Rotating just the
            # ``celery_task_id`` — not ``execution_id`` — sidesteps the
            # revoke list while keeping the execution-scoped state
            # (ExecutionState, positions, events, trades, ...) continuous
            # across the resume.
            if locked_task.status in (TaskStatus.STOPPED, TaskStatus.FAILED):
                if previous_celery_task_id:
                    try:
                        self._revoke_execution(previous_celery_task_id)
                    except Exception as exc:  # pragma: no cover - best effort
                        self.logger.debug(
                            "Pre-resume revoke skipped - task_id=%s, error=%s",
                            task_id,
                            exc,
                        )

            # Clear error fields when resuming from a terminal state so the
            # execution starts cleanly while preserving execution_id and
            # all persisted state (strategy_state, events, positions, etc.).
            update_fields = ["status", "updated_at"]
            if locked_task.status in (TaskStatus.STOPPED, TaskStatus.FAILED):
                locked_task.error_message = None
                locked_task.error_traceback = None
                locked_task.completed_at = None
                update_fields += [
                    "error_message",
                    "error_traceback",
                    "completed_at",
                ]

            # Always rotate the Celery task id on resume so the next
            # worker invocation is guaranteed to be accepted.
            locked_task.celery_task_id = uuid4()
            update_fields.append("celery_task_id")

            locked_task.status = TaskStatus.STARTING
            locked_task.save(update_fields=update_fields)
            self._audit_lifecycle_transition(
                command="resume",
                task_id=locked_task.pk,
                task_type=task_type,
                from_status=previous_status,
                to_status=locked_task.status,
                execution_id=locked_task.execution_id,
                celery_task_id=locked_task.celery_task_id,
            )
            task = locked_task

        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_resume_requested",
            description=f"Task resume requested (from {locked_task.status})",
        )
        self.service._dispatch_task(task, task_type)
        if is_trading:
            self._kick_market_supervisor()
        return task

    def _prepare_start(
        self,
        *,
        task: BacktestTask | TradingTask,
        model_class: type[BacktestTask] | type[TradingTask],
    ) -> BacktestTask | TradingTask:
        if type(task) in (BacktestTask, TradingTask):
            return self.service._prepare_locked_start_task(task, model_class=model_class)
        return self.service._prepare_detached_start_task(task)

    def _reset_failed_start(
        self,
        *,
        task: BacktestTask | TradingTask,
        model_class: type[BacktestTask] | type[TradingTask],
    ) -> None:
        if type(task) in (BacktestTask, TradingTask):
            model_class.objects.filter(pk=task.pk).update(
                status=TaskStatus.CREATED,
                execution_id=None,
                celery_task_id=None,
            )
            task.refresh_from_db()
            return

        task.status = TaskStatus.CREATED
        task.execution_id = None
        task.celery_task_id = None
        try:
            task.save(update_fields=["status", "execution_id", "celery_task_id"])
        except TypeError:
            task.save()

    def _log_worker_state(self, task: BacktestTask | TradingTask) -> None:
        active_workers = self.adapters.inspect_workers()
        if not active_workers:
            self.logger.warning(
                "[SERVICE:START] NO_WORKERS - No active Celery workers detected. task_id=%s, execution_id=%s",
                task.pk,
                task.execution_id,
            )
            return
        self.logger.info(
            "[SERVICE:START] Active workers found - task_id=%s, workers=%s",
            task.pk,
            list(active_workers.keys()),
        )

    def _signal_redis_stop(
        self,
        *,
        task_id: UUID,
        task_name: str,
        execution_id: object,
    ) -> None:
        try:
            self.adapters.signal_stop(task_id, task_name, execution_id)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:STOP] Redis signal failed (non-fatal) - task_id=%s, error=%s",
                task_id,
                exc,
            )

    def _signal_redis_pause(
        self,
        *,
        task_id: UUID,
        task_name: str,
        execution_id: object,
    ) -> None:
        try:
            self.adapters.signal_pause(task_id, task_name, execution_id)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:PAUSE] Redis signal failed (non-fatal) - task_id=%s, error=%s",
                task_id,
                exc,
            )

    def _revoke_execution(self, celery_task_id: object) -> None:
        try:
            self.adapters.revoke_execution(celery_task_id)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:LIFECYCLE] Celery revoke failed (non-fatal) - celery_task_id=%s, error=%s",
                celery_task_id,
                exc,
            )

    def _trigger_stop_task(
        self,
        *,
        task_id: UUID,
        is_backtest: bool,
        stop_mode: StopMode,
    ) -> None:
        try:
            self.adapters.dispatch_stop(task_id, is_backtest, stop_mode)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:STOP] Stop task trigger failed (non-fatal) - task_id=%s, error=%s",
                task_id,
                exc,
            )

    def _record_drain_duration_minutes_override(
        self,
        *,
        task_id: UUID,
        task_type: str,
        execution_id: object,
        minutes: int,
    ) -> None:
        """Store a per-stop drain duration override on the execution state.

        The executor reads this value on the next drain evaluation and
        prefers it over the task-level ``drain_duration_hours``.  A
        missing or zero value means "fall back to the task field".
        """
        from apps.trading.models import ExecutionState

        try:
            state = ExecutionState.objects.filter(
                task_type=task_type,
                task_id=task_id,
                execution_id=execution_id,
            ).first()
            if state is None:
                self.logger.debug(
                    "[SERVICE:STOP] No ExecutionState to record drain override - "
                    "task_id=%s execution_id=%s",
                    task_id,
                    execution_id,
                )
                return
            strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
            strategy_state["_drain_duration_minutes_override"] = int(minutes)
            state.strategy_state = strategy_state
            state.save(update_fields=["strategy_state", "updated_at"])
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.warning(
                "[SERVICE:STOP] Failed to record drain duration override - task_id=%s error=%s",
                task_id,
                exc,
            )

    def _ensure_resumeable_celery_state(
        self,
        *,
        result: AsyncResult | None,
        task_id: UUID,
        db_status: TaskStatus,
        celery_task_id: object,
    ) -> None:
        if not result:
            return
        celery_state = result.state
        # For STOPPED/FAILED tasks the worker has already exited — the
        # Celery result backend may still report STARTED if the previous
        # worker crashed before updating the backend.  Since the DB is
        # the authoritative state for task lifecycle, skip the Celery
        # guard for terminal DB statuses and allow the resume to proceed.
        if db_status in (TaskStatus.STOPPED, TaskStatus.FAILED):
            if celery_state in ["PENDING", "STARTED", "RETRY"]:
                self.logger.info(
                    "Stale Celery state detected for terminal task; "
                    "proceeding with resume - task_id=%s, db_status=%s, "
                    "celery_state=%s, celery_task_id=%s",
                    task_id,
                    db_status,
                    celery_state,
                    celery_task_id,
                )
            return

        if celery_state in ["PENDING", "STARTED", "RETRY"]:
            self.logger.warning(
                "Task status mismatch detected",
                extra={
                    "task_id": str(task_id),
                    "db_status": db_status,
                    "celery_state": celery_state,
                    "celery_task_id": str(celery_task_id),
                },
            )
            from apps.trading.tasks.service import TaskValidationError

            raise TaskValidationError(
                f"Task status mismatch: task is marked as {db_status} in database "
                f"but Celery task is still {celery_state}. "
                "Please wait for the task to fully stop before resuming."
            )

    def _assert_transition_allowed(
        self,
        *,
        command: str,
        task_status: TaskStatus,
        message: str,
    ) -> None:
        allowed = allowed_statuses_for_command(command)
        if not allowed or task_status in allowed:
            return
        from apps.trading.tasks.service import TaskValidationError

        raise TaskValidationError(message)

    def _audit_lifecycle_transition(
        self,
        *,
        command: str,
        task_id: UUID,
        task_type: str,
        from_status: TaskStatus | str,
        to_status: TaskStatus | str,
        execution_id: object,
        celery_task_id: object,
        **extra: object,
    ) -> None:
        payload: dict[str, object] = {
            "command": command,
            "task_id": str(task_id),
            "task_type": task_type,
            "from_status": str(from_status),
            "to_status": str(to_status),
            "execution_id": str(execution_id) if execution_id else "",
            "celery_task_id": str(celery_task_id) if celery_task_id else "",
        }
        payload.update(extra)
        self.logger.info("[LIFECYCLE:AUDIT] %s", payload)
