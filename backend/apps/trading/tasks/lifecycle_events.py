"""Lifecycle event publishing for task state transitions."""

from __future__ import annotations

from logging import Logger

from apps.trading.models import BacktestTask, TradingEvent, TradingTask


class TaskLifecycleEventPublisher:
    """Persist lifecycle events emitted by task lifecycle commands."""

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def publish(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
        kind: str,
        description: str,
        extra_details: dict[str, object] | None = None,
    ) -> None:
        details = {
            "kind": kind,
            "status": str(task.status),
            "task_name": str(getattr(task, "name", "")),
        }
        if extra_details:
            details.update(extra_details)

        try:
            TradingEvent.objects.create(
                event_type="status_changed",
                severity="info",
                description=description,
                user=getattr(task, "user", None),
                account=getattr(task, "oanda_account", None),
                instrument=getattr(task, "instrument", None),
                task_type=task_type,
                task_id=task.pk,
                execution_id=getattr(task, "execution_id", None),
                details=details,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            self.logger.warning(
                "[SERVICE:EVENT] Failed to persist lifecycle event - task_id=%s, kind=%s, error=%s",
                task.pk,
                kind,
                exc,
            )
