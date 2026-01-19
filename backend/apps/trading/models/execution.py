"""Task execution models."""

import traceback
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.trading.enums import TaskStatus, TaskType

if TYPE_CHECKING:
    from apps.trading.models.events import StrategyEvents
    from apps.trading.models.state import ExecutionStateSnapshot


class ExecutionsManager(models.Manager["Executions"]):
    """Custom manager for Executions model."""

    def for_task(self, task_type: str, task_id: int) -> models.QuerySet["Executions"]:
        """Get all executions for a specific task."""
        return self.filter(task_type=task_type, task_id=task_id)

    def running(self) -> models.QuerySet["Executions"]:
        """Get all running executions."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["Executions"]:
        """Get all completed executions."""
        return self.filter(status=TaskStatus.COMPLETED)

    def failed(self) -> models.QuerySet["Executions"]:
        """Get all failed executions."""
        return self.filter(status=TaskStatus.FAILED)


class Executions(models.Model):
    """
    Track individual execution runs of tasks.

    This model records each execution attempt of a backtest or trading task,
    including status, timing, and error information.
    """

    objects = ExecutionsManager()

    if TYPE_CHECKING:
        # Type stubs for reverse relationships
        state_snapshots: models.Manager["ExecutionStateSnapshot"]
        strategy_events: models.Manager["StrategyEvents"]

    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.IntegerField(
        help_text="ID of the parent task",
    )
    execution_number = models.IntegerField(
        help_text="Sequential execution number for the task",
    )
    status = models.CharField(
        max_length=20,
        default=TaskStatus.CREATED,
        choices=TaskStatus.choices,
        db_index=True,
        help_text="Current execution status",
    )
    progress = models.IntegerField(
        default=0,
        help_text="Execution progress percentage (0-100)",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Execution start timestamp",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Execution completion timestamp",
    )
    cpu_limit_cores = models.IntegerField(
        null=True,
        blank=True,
        help_text="CPU cores limit configured for execution",
    )
    memory_limit_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Memory limit in MB configured for execution",
    )
    peak_memory_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peak memory usage in MB during execution",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if execution failed",
    )
    error_traceback = models.TextField(
        blank=True,
        default="",
        help_text="Full traceback for debugging",
    )
    logs = models.JSONField(
        default=list,
        blank=True,
        help_text="Execution logs as list of {timestamp, level, message} objects",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Record creation timestamp",
    )

    class Meta:
        db_table = "executions"
        verbose_name = "Execution"
        verbose_name_plural = "Executions"
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_number"],
                name="unique_task_execution",
            )
        ]
        indexes = [
            models.Index(fields=["task_type", "task_id", "created_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"{self.task_type} Task {self.task_id} - "
            f"Execution #{self.execution_number} ({self.status})"
        )

    def mark_completed(self) -> None:
        """Mark execution as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = timezone.now()
        self.progress = 100
        # Include logs in save to ensure they're persisted
        self.save(update_fields=["status", "completed_at", "progress", "logs"])

    def update_progress(self, progress: int) -> None:
        """
        Update execution progress.

        Args:
            progress: Progress percentage (0-100)
        """
        self.progress = max(0, min(100, progress))
        self.save(update_fields=["progress"])

    def add_log(self, level: str, message: str) -> None:
        """
        Add a log entry to the execution logs.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
        """
        log_entry = {
            "timestamp": timezone.now().isoformat(),
            "level": level,
            "message": message,
        }
        if not isinstance(self.logs, list):
            self.logs = []
        self.logs.append(log_entry)
        self.save(update_fields=["logs"])

    def mark_failed(self, error: Exception) -> None:
        """
        Mark execution as failed with error details.

        Args:
            error: Exception that caused the failure
        """
        self.status = TaskStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = str(error)
        self.error_traceback = traceback.format_exc()
        # Include logs in save to ensure they're persisted even on failure
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_traceback", "logs"]
        )

    def get_duration(self) -> str | None:
        """
        Calculate execution duration.

        Returns:
            Duration as a formatted string, or None if not completed
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            total_seconds = delta.total_seconds()

            if total_seconds < 60:
                return f"{total_seconds:.0f}s"
            if total_seconds < 3600:
                minutes = total_seconds / 60
                return f"{minutes:.1f}m"
            if total_seconds < 86400:
                hours = total_seconds / 3600
                return f"{hours:.1f}h"
            days = total_seconds / 86400
            return f"{days:.1f}d"
        return None

    # State Management Methods

    def save_state_snapshot(
        self,
        strategy_state: dict,
        current_balance,
        open_positions: list,
        ticks_processed: int,
        last_tick_timestamp: str = "",
        metrics: dict | None = None,
    ) -> "ExecutionStateSnapshot":  # type: ignore[name-defined]
        """
        Save a state snapshot for this execution.

        Creates a new ExecutionStateSnapshot with a monotonically increasing
        sequence number, enabling task resumability.

        Args:
            strategy_state: Strategy-specific state dictionary
            current_balance: Current account balance (Decimal or numeric)
            open_positions: List of open position dictionaries
            ticks_processed: Number of ticks processed so far
            last_tick_timestamp: ISO format timestamp of last processed tick
            metrics: Current performance metrics dictionary

        Returns:
            The created ExecutionStateSnapshot instance"""
        from decimal import Decimal

        from apps.trading.models.state import ExecutionStateSnapshot

        sequence = self._next_snapshot_sequence()

        snapshot = ExecutionStateSnapshot.objects.create(
            execution=self,
            sequence=sequence,
            strategy_state=strategy_state or {},
            current_balance=Decimal(str(current_balance)),
            open_positions=open_positions or [],
            ticks_processed=ticks_processed,
            last_tick_timestamp=last_tick_timestamp,
            metrics=metrics or {},
        )

        return snapshot

    def load_latest_state(self) -> dict | None:
        """
        Load the most recent state snapshot for this execution.

        Returns a dictionary containing the state data, or None if no
        snapshots exist. This enables resuming execution from the last
        saved state.

        Returns:
            Dictionary with keys: strategy_state, current_balance,
            open_positions, ticks_processed, last_tick_timestamp, metrics.
            Returns None if no snapshots exist."""
        snapshot = self.state_snapshots.order_by("-sequence").first()

        if snapshot is None:
            return None

        return {
            "strategy_state": snapshot.strategy_state,
            "current_balance": snapshot.current_balance,
            "open_positions": snapshot.open_positions,
            "ticks_processed": snapshot.ticks_processed,
            "last_tick_timestamp": snapshot.last_tick_timestamp,
            "metrics": snapshot.metrics,
            "sequence": snapshot.sequence,
        }

    def _next_snapshot_sequence(self) -> int:
        """
        Get the next sequence number for state snapshots.

        Returns:
            Next monotonic sequence number (0-indexed)"""
        last_snapshot = self.state_snapshots.order_by("-sequence").first()
        return (last_snapshot.sequence + 1) if last_snapshot else 0

    # Event Emission Methods

    def emit_event(
        self,
        event_type: str,
        event_data: dict,
        strategy_type: str = "",
        timestamp: str | None = None,
    ) -> "StrategyEvents":  # type: ignore[name-defined]
        """
        Emit a strategy event for this execution.

        Creates a new StrategyEvents with a monotonically increasing
        sequence number. Events are persisted to enable real-time monitoring
        and post-execution analysis.

        Args:
            event_type: Type of event (e.g., 'tick_received', 'trade_executed')
            event_data: Event payload dictionary
            strategy_type: Strategy type identifier (e.g., 'floor', 'momentum')
            timestamp: Event timestamp (ISO format string), parsed if provided

        Returns:
            The created StrategyEvents instance"""
        from django.utils.dateparse import parse_datetime

        from apps.trading.models.events import StrategyEvents

        sequence = self._next_event_sequence()

        # Parse timestamp if provided
        parsed_timestamp = None
        if timestamp:
            parsed_timestamp = parse_datetime(timestamp)

        event = StrategyEvents.objects.create(
            execution=self,
            sequence=sequence,
            event_type=event_type,
            strategy_type=strategy_type,
            timestamp=parsed_timestamp,
            event=event_data or {},
        )

        return event

    def _next_event_sequence(self) -> int:
        """
        Get the next sequence number for strategy events.

        Returns:
            Next monotonic sequence number (0-indexed)"""
        last_event = self.strategy_events.order_by("-sequence").first()
        return (last_event.sequence + 1) if last_event else 0


class TaskExecutionResult(models.Model):
    """Persistent summary of an execution attempt."""

    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.IntegerField(
        db_index=True,
        help_text="ID of the task that was executed (matches TaskExecution.task_id)",
    )
    execution = models.OneToOneField(
        "trading.Executions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="result",
        help_text="Associated Executions record (if created)",
    )
    success = models.BooleanField(
        default=False,
        help_text="Whether execution completed successfully",
    )
    error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if failed",
    )
    account = models.ForeignKey(
        OandaAccounts,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_execution_results",
        help_text="OANDA account used (for trading tasks)",
    )
    oanda_account_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="OANDA account ID string (for trading tasks)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the result record was created",
    )

    class Meta:
        db_table = "task_execution_results"
        verbose_name = "Task Execution Result"
        verbose_name_plural = "Task Execution Results"
        indexes = [
            models.Index(fields=["task_type", "task_id", "created_at"]),
            models.Index(fields=["success"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.task_type} Task {self.task_id} - {'success' if self.success else 'failed'}"
