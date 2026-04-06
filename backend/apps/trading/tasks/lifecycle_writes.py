"""Write-side helpers for task lifecycle transitions."""

from __future__ import annotations

from logging import Logger

from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, TradingTask


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
        status: TaskStatus,
        extra_updates: dict[str, object] | None = None,
    ) -> None:
        terminal_updates = {"completed_at": timezone.now(), **(extra_updates or {})}
        self.persist_state(task, status=status, extra_updates=terminal_updates)

    def clear_execution_history(
        self,
        *,
        task: BacktestTask | TradingTask,
        task_type: str,
    ) -> None:
        """No-op: execution data is scoped by execution_id.

        A new execution_id is assigned on each restart, so previous
        runs' ExecutionState, TradingEvent, and StrategyEventRecord
        rows do not interfere and must be preserved for historical
        viewing.
        """
