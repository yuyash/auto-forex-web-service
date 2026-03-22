"""Lifecycle event publishing for task state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Callable, Protocol

from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models.celery import CeleryTaskStatus
from apps.trading.models import BacktestTask, TaskLog, TradingEvent, TradingTask
from apps.trading.services.execution_lifecycle import (
    sync_terminal_execution_artifacts,
    transition_task_to_stopped,
    transition_task_to_terminal,
)


@dataclass(frozen=True)
class TaskLifecycleEvent:
    """Lifecycle event payload shared by publishers."""

    task: BacktestTask | TradingTask
    task_type: str
    kind: str
    description: str
    extra_details: dict[str, object] | None = None
    log_level: LogLevel | None = None
    log_message: str | None = None
    log_component: str | None = None

    @property
    def details(self) -> dict[str, object]:
        details = {
            "kind": self.kind,
            "status": str(self.task.status),
            "task_name": str(getattr(self.task, "name", "")),
        }
        if self.extra_details:
            details.update(self.extra_details)
        return details


class TaskLifecycleEventSink(Protocol):
    """Sink for lifecycle event side effects."""

    def publish(self, event: TaskLifecycleEvent) -> None:
        """Handle a lifecycle event."""


class LoggerLifecycleEventSink:
    """Emit lifecycle events to structured application logs."""

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def publish(self, event: TaskLifecycleEvent) -> None:
        self.logger.info(
            "[SERVICE:EVENT] Lifecycle event published - task_id=%s, task_type=%s, kind=%s, status=%s",
            event.task.pk,
            event.task_type,
            event.kind,
            event.task.status,
        )


class CallbackLifecycleEventSink:
    """Forward lifecycle events to an injected callback for notifications."""

    def __init__(self, *, callback: Callable[[TaskLifecycleEvent], None]) -> None:
        self.callback = callback

    def publish(self, event: TaskLifecycleEvent) -> None:
        self.callback(event)


class TaskLogLifecycleSink:
    """Persist lifecycle logs through the same event pipeline."""

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def publish(self, event: TaskLifecycleEvent) -> None:
        if event.log_level is None or not event.log_message or not event.log_component:
            return
        try:
            TaskLog.objects.create(
                task_type=event.task_type,
                task_id=event.task.pk,
                execution_id=getattr(event.task, "execution_id", None),
                level=event.log_level,
                component=event.log_component,
                message=event.log_message,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:EVENT] Failed to persist task lifecycle log - task_id=%s, kind=%s, error=%s",
                event.task.pk,
                event.kind,
                exc,
            )


class TradingEventLifecycleSink:
    """Persist lifecycle events as TradingEvent rows."""

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def publish(self, event: TaskLifecycleEvent) -> None:
        try:
            TradingEvent.objects.create(
                event_type="status_changed",
                severity="info",
                description=event.description,
                user=getattr(event.task, "user", None),
                account=getattr(event.task, "oanda_account", None),
                instrument=getattr(event.task, "instrument", None),
                task_type=event.task_type,
                task_id=event.task.pk,
                execution_id=getattr(event.task, "execution_id", None),
                details=event.details,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:EVENT] Failed to persist lifecycle event - task_id=%s, kind=%s, error=%s",
                event.task.pk,
                event.kind,
                exc,
            )


class CeleryTaskStatusLifecycleSink:
    """Persist terminal trading task lifecycle status in CeleryTaskStatus."""

    task_name_map = {
        "backtest": "trading.tasks.run_backtest_task",
        "trading": "trading.tasks.run_trading_task",
    }
    terminal_status_map = {
        str(TaskStatus.STOPPED): CeleryTaskStatus.Status.STOPPED,
        str(TaskStatus.COMPLETED): CeleryTaskStatus.Status.COMPLETED,
        str(TaskStatus.FAILED): CeleryTaskStatus.Status.FAILED,
    }

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def publish(self, event: TaskLifecycleEvent) -> None:
        execution_id = getattr(event.task, "execution_id", None)
        task_name = self.task_name_map.get(str(event.task_type))
        if not execution_id or not task_name:
            return

        status = self.terminal_status_map.get(str(event.task.status))
        if status is None:
            return

        now = timezone.now()
        updates: dict[str, object] = {
            "status": status,
            "stopped_at": now,
            "last_heartbeat_at": now,
        }
        if status == CeleryTaskStatus.Status.FAILED:
            updates["status_message"] = event.description

        try:
            CeleryTaskStatus.objects.filter(
                task_name=task_name,
                instance_key=f"{event.task.pk}:{execution_id}",
            ).update(**updates)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:EVENT] Failed to persist CeleryTaskStatus - task_id=%s, kind=%s, error=%s",
                event.task.pk,
                event.kind,
                exc,
            )


class ExecutionArtifactsLifecycleSink:
    """Refresh execution read models for terminal lifecycle events."""

    terminal_kinds = frozenset({"task_cancelled"})

    def __init__(
        self,
        *,
        logger: Logger,
        sync_artifacts: Callable[..., None] = sync_terminal_execution_artifacts,
    ) -> None:
        self.logger = logger
        self.sync_artifacts = sync_artifacts

    def publish(self, event: TaskLifecycleEvent) -> None:
        if event.kind not in self.terminal_kinds:
            return
        try:
            self.sync_artifacts(task=event.task, task_type=event.task_type)
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:EVENT] Failed to sync execution artifacts - task_id=%s, kind=%s, error=%s",
                event.task.pk,
                event.kind,
                exc,
            )


class TaskLifecycleEventPublisher:
    """Dispatch lifecycle events to configured sinks."""

    def __init__(
        self,
        *,
        logger: Logger,
        sinks: tuple[TaskLifecycleEventSink, ...] | None = None,
    ) -> None:
        self.logger = logger
        self.sinks = sinks or (
            LoggerLifecycleEventSink(logger=logger),
            TaskLogLifecycleSink(logger=logger),
            CeleryTaskStatusLifecycleSink(logger=logger),
            ExecutionArtifactsLifecycleSink(logger=logger),
            TradingEventLifecycleSink(logger=logger),
        )

    def publish(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
        kind: str,
        description: str,
        extra_details: dict[str, object] | None = None,
        log_level: LogLevel | None = None,
        log_message: str | None = None,
        log_component: str | None = None,
    ) -> None:
        event = TaskLifecycleEvent(
            task=task,
            task_type=task_type,
            kind=kind,
            description=description,
            extra_details=extra_details,
            log_level=log_level,
            log_message=log_message,
            log_component=log_component,
        )
        for sink in self.sinks:
            sink.publish(event)


def publish_task_lifecycle_event(
    *,
    logger: Logger,
    task: BacktestTask | TradingTask,
    task_type: str,
    kind: str,
    description: str,
    extra_details: dict[str, object] | None = None,
    log_level: LogLevel | None = None,
    log_message: str | None = None,
    log_component: str | None = None,
) -> None:
    """Publish a lifecycle event through the default sink pipeline."""

    TaskLifecycleEventPublisher(logger=logger).publish(
        task=task,
        task_type=task_type,
        kind=kind,
        description=description,
        extra_details=extra_details,
        log_level=log_level,
        log_message=log_message,
        log_component=log_component,
    )


def finalize_task_terminal_lifecycle(
    *,
    logger: Logger,
    task: BacktestTask | TradingTask,
    task_type: str,
    status: TaskStatus,
    kind: str,
    description: str,
    expected_current_status: TaskStatus | None = None,
    extra_details: dict[str, object] | None = None,
    error_message: str | None = None,
    error_traceback: str | None = None,
    log_level: LogLevel | None = None,
    log_message: str | None = None,
    log_component: str | None = None,
) -> int:
    """Persist a terminal task transition and publish its lifecycle event."""

    if status == TaskStatus.STOPPED:
        rows_updated = transition_task_to_stopped(
            task=task,
            task_type=task_type,
            expected_current_status=expected_current_status,
        )
    else:
        rows_updated = transition_task_to_terminal(
            task=task,
            task_type=task_type,
            status=status,
            expected_current_status=expected_current_status,
            error_message=error_message,
            error_traceback=error_traceback,
        )

    if rows_updated > 0:
        publish_task_lifecycle_event(
            logger=logger,
            task=task,
            task_type=task_type,
            kind=kind,
            description=description,
            extra_details=extra_details,
            log_level=log_level,
            log_message=log_message,
            log_component=log_component,
        )
    return rows_updated
