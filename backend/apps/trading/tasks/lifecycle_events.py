"""Lifecycle event publishing for task state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Callable, Protocol

from apps.trading.models import BacktestTask, TradingEvent, TradingTask
from apps.trading.services.execution_lifecycle import sync_terminal_execution_artifacts


@dataclass(frozen=True)
class TaskLifecycleEvent:
    """Lifecycle event payload shared by publishers."""

    task: BacktestTask | TradingTask
    task_type: str
    kind: str
    description: str
    extra_details: dict[str, object] | None = None

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
    ) -> None:
        event = TaskLifecycleEvent(
            task=task,
            task_type=task_type,
            kind=kind,
            description=description,
            extra_details=extra_details,
        )
        for sink in self.sinks:
            sink.publish(event)
