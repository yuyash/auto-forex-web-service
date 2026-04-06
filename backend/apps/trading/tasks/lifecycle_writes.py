"""Write-side helpers for task lifecycle transitions."""

from __future__ import annotations

from logging import Logger

from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, StrategyEventRecord, TradingEvent, TradingTask


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
        from apps.trading.models.equities import Equity
        from apps.trading.models.logs import TaskLog
        from apps.trading.models.metrics import Metrics
        from apps.trading.models.orders import Order
        from apps.trading.models.positions import Position
        from apps.trading.models.snapshots import TaskExecutionSnapshot
        from apps.trading.models.state import ExecutionState
        from apps.trading.models.trades import Trade

        for model, label in (
            (Trade, "trades"),
            (Order, "orders"),
            (Position, "positions"),
            (TradingEvent, "trading events"),
            (StrategyEventRecord, "strategy events"),
            (ExecutionState, "execution state"),
            (Equity, "equities"),
            (Metrics, "metrics"),
            (TaskExecutionSnapshot, "execution snapshots"),
            (TaskLog, "task logs"),
        ):
            try:
                deleted, _ = model.objects.filter(task_type=task_type, task_id=task.pk).delete()
                if deleted:
                    self.logger.info(
                        "[SERVICE:RESTART] Cleared %d %s - task_id=%s",
                        deleted,
                        label,
                        task.pk,
                    )
            except Exception as exc:  # pragma: no cover - defensive logging path
                self.logger.warning(
                    "[SERVICE:RESTART] Failed to clear %s - task_id=%s, error=%s",
                    label,
                    task.pk,
                    exc,
                )
