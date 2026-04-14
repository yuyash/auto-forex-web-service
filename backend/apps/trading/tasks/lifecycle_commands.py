"""Command objects for task lifecycle orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from logging import Logger
from typing import TYPE_CHECKING, Callable, cast
from uuid import UUID

from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction

from apps.trading.enums import StopMode, TaskStatus
from apps.trading.models import BacktestTask, TradingTask
from apps.trading.tasks.lifecycle_events import TaskLifecycleEventPublisher

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


def _default_revoke_execution(execution_id: object) -> None:
    from celery import current_app

    current_app.control.revoke(str(execution_id), terminate=True, signal="SIGKILL")


def _default_dispatch_stop(task_id: UUID, is_backtest: bool, stop_mode: StopMode) -> None:
    from apps.trading.tasks import service as service_module

    if is_backtest:
        service_module.stop_backtest_task.apply_async(args=[task_id], queue="system")
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

    def stop(self, task_id: UUID, mode: str = "graceful") -> bool:
        self.logger.info("[SERVICE:STOP] Stopping task - task_id=%s, mode=%s", task_id, mode)
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

        if task.status in [TaskStatus.STOPPED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.logger.info(
                "[SERVICE:STOP] Already in terminal state: %s - task_id=%s",
                task.status,
                task_id,
            )
            return True

        task.status = TaskStatus.STOPPING
        update_fields = ["status", "updated_at"]
        if not is_backtest and stop_mode == StopMode.GRACEFUL_CLOSE:
            trading_task = cast(TradingTask, task)
            trading_task.sell_on_stop = True
            update_fields.append("sell_on_stop")
        task.save(update_fields=update_fields)

        self._signal_redis_stop(
            task_id=task_id, task_name=task_name, execution_id=task.execution_id
        )
        if stop_mode == StopMode.IMMEDIATE and task.execution_id:
            self._revoke_execution(task.execution_id)
        self._trigger_stop_task(task_id=task_id, is_backtest=is_backtest, stop_mode=stop_mode)

        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_stop_requested",
            description="Task stop requested",
            extra_details={"mode": stop_mode.value},
        )
        return True

    def pause(self, task_id: UUID) -> bool:
        task, task_type = self.service._get_task_and_type(task_id)
        self.service._ensure_task_status(
            task,
            allowed=(TaskStatus.STARTING, TaskStatus.RUNNING),
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

        result = self.service.get_celery_result(
            str(task.execution_id) if task.execution_id else None
        )
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

        if task.execution_id:
            self._revoke_execution(task.execution_id)

        self.service.writer.clear_execution_history(task=task, task_type=task_type)
        type(task).objects.filter(pk=task.pk).update(
            execution_id=None,
            status=TaskStatus.CREATED,
            started_at=None,
            completed_at=None,
            error_message=None,
            error_traceback=None,
        )
        task.refresh_from_db()
        if task.status != TaskStatus.CREATED:
            raise RuntimeError(f"Failed to reset task status: expected CREATED, got {task.status}")
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

        with transaction.atomic():
            locked_task = model_class.objects.select_for_update().get(pk=task.pk)
            if locked_task.status != TaskStatus.PAUSED:
                raise ValueError(
                    f"Task cannot be resumed from {locked_task.status} state. "
                    "Only PAUSED tasks can be resumed."
                )
            if not locked_task.execution_id:
                raise ValueError("Cannot resume task without an execution_id")

            result = self.service.get_celery_result(str(locked_task.execution_id))
            self._ensure_resumeable_celery_state(
                result=result,
                task_id=task_id,
                db_status=locked_task.status,
                execution_id=locked_task.execution_id,
            )
            locked_task.status = TaskStatus.STARTING
            locked_task.save(update_fields=["status", "updated_at"])
            task = locked_task

        self.events.publish(
            task=task,
            task_type=task_type,
            kind="task_resume_requested",
            description="Task resume requested",
        )
        self.service._dispatch_task(task, task_type)
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
            )
            task.refresh_from_db()
            return

        task.status = TaskStatus.CREATED
        task.execution_id = None
        try:
            task.save(update_fields=["status", "execution_id"])
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

    def _revoke_execution(self, execution_id: object) -> None:
        try:
            self.adapters.revoke_execution(execution_id)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:LIFECYCLE] Celery revoke failed (non-fatal) - execution_id=%s, error=%s",
                execution_id,
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

    def _ensure_resumeable_celery_state(
        self,
        *,
        result: AsyncResult | None,
        task_id: UUID,
        db_status: TaskStatus,
        execution_id: object,
    ) -> None:
        if not result:
            return
        celery_state = result.state
        if celery_state in ["PENDING", "STARTED", "RETRY"]:
            self.logger.warning(
                "Task status mismatch detected",
                extra={
                    "task_id": str(task_id),
                    "db_status": db_status,
                    "celery_state": celery_state,
                    "execution_id": str(execution_id),
                },
            )
            raise ValueError(
                "Task status mismatch: task is marked as PAUSED in database "
                f"but Celery task is still {celery_state}. "
                "Please wait for the task to fully stop before resuming."
            )
