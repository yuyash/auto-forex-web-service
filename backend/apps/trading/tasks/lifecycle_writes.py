"""Write-side helpers for task lifecycle transitions."""

from __future__ import annotations

from logging import Logger

from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, StrategyEventRecord, TradingEvent, TradingTask
from apps.trading.services.execution_lifecycle import sync_terminal_execution_artifacts


class TaskLifecycleWriter:
    """Encapsulate lifecycle write operations and cleanup side effects."""

    def __init__(self, *, logger: Logger) -> None:
        self.logger = logger

    def persist_state(
        self,
        task: BacktestTask | TradingTask,
        *,
        status: TaskStatus,
        extra_updates: dict[str, object] | None = None,
    ) -> None:
        extra_updates = extra_updates or {}
        for field, value in extra_updates.items():
            setattr(task, field, value)
        task.status = status
        task.save(update_fields=["status", "updated_at", *extra_updates.keys()])

    def finalize_terminal_task(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
        status: TaskStatus,
        extra_updates: dict[str, object] | None = None,
        sync_artifacts=sync_terminal_execution_artifacts,
    ) -> None:
        terminal_updates = {"completed_at": timezone.now(), **(extra_updates or {})}
        self.persist_state(task, status=status, extra_updates=terminal_updates)
        sync_artifacts(task=task, task_type=task_type)

    def clear_execution_history(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
    ) -> None:
        from apps.trading.models.state import ExecutionState

        for model, label in (
            (TradingEvent, "trading events"),
            (StrategyEventRecord, "strategy events"),
            (ExecutionState, "execution state"),
        ):
            try:
                model.objects.filter(task_type=task_type, task_id=task.pk).delete()
            except Exception as exc:  # pragma: no cover - defensive logging path
                self.logger.warning(
                    "[SERVICE:RESTART] Failed to clear %s - task_id=%s, error=%s",
                    label,
                    task.pk,
                    exc,
                )
