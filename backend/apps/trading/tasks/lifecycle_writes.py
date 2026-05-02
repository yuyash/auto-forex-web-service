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

    @staticmethod
    def now():
        """Return the current timestamp for lifecycle writes."""

        return timezone.now()

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
        terminal_updates = {"completed_at": self.now(), **(extra_updates or {})}
        self.persist_state(task, status=status, extra_updates=terminal_updates)

    def persist_state_if_current(
        self,
        *,
        command: str,
        task: BacktestTask | TradingTask,
        from_status: TaskStatus | str,
        to_status: TaskStatus,
        extra_updates: dict[str, object] | None = None,
    ) -> None:
        """Persist a status transition only if the task is still in the expected state."""

        updates: dict[str, object] = {"status": to_status, **(extra_updates or {})}
        self.update_if_current(
            command=command,
            task=task,
            expected_status=from_status,
            updates=updates,
        )

    def persist_terminal_state_if_current(
        self,
        *,
        command: str,
        task: BacktestTask | TradingTask,
        from_status: TaskStatus | str,
        to_status: TaskStatus,
        extra_updates: dict[str, object] | None = None,
    ) -> None:
        """Persist a terminal transition only if the source state still matches."""

        terminal_updates = {"completed_at": self.now(), **(extra_updates or {})}
        self.persist_state_if_current(
            command=command,
            task=task,
            from_status=from_status,
            to_status=to_status,
            extra_updates=terminal_updates,
        )

    def update_if_current(
        self,
        *,
        command: str,
        task: BacktestTask | TradingTask,
        expected_status: TaskStatus | str,
        updates: dict[str, object],
    ) -> None:
        """Apply updates only if the persisted task status still matches."""

        model_objects = getattr(type(task), "objects", None)
        update_values = {"updated_at": self.now(), **updates}

        if model_objects is None:
            self._save_detached_task_update(task=task, updates=update_values)
            return

        rows_updated = model_objects.filter(pk=task.pk, status=expected_status).update(
            **update_values
        )
        if rows_updated == 0:
            refresh_from_db = getattr(task, "refresh_from_db", None)
            if callable(refresh_from_db):
                refresh_from_db()
            from apps.trading.tasks.service import TaskConflictError

            raise TaskConflictError(
                f"Task {command} was superseded by another lifecycle transition. "
                "Reload the task before retrying."
            )

        for field, value in update_values.items():
            setattr(task, field, value)

    @staticmethod
    def _save_detached_task_update(
        *,
        task: BacktestTask | TradingTask,
        updates: dict[str, object],
    ) -> None:
        for field, value in updates.items():
            setattr(task, field, value)
        try:
            task.save(update_fields=list(updates.keys()))
        except TypeError:
            task.save()

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
