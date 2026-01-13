"""Task execution models."""

import traceback

from django.db import models
from django.utils import timezone

from apps.market.models import OandaAccount
from apps.trading.enums import TaskStatus, TaskType


class TaskExecutionManager(models.Manager["TaskExecution"]):
    """Custom manager for TaskExecution model."""

    def for_task(self, task_type: str, task_id: int) -> models.QuerySet["TaskExecution"]:
        """Get all executions for a specific task."""
        return self.filter(task_type=task_type, task_id=task_id)

    def running(self) -> models.QuerySet["TaskExecution"]:
        """Get all running executions."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["TaskExecution"]:
        """Get all completed executions."""
        return self.filter(status=TaskStatus.COMPLETED)

    def failed(self) -> models.QuerySet["TaskExecution"]:
        """Get all failed executions."""
        return self.filter(status=TaskStatus.FAILED)


class TaskExecution(models.Model):
    """
    Track individual execution runs of tasks.

    This model records each execution attempt of a backtest or trading task,
    including status, timing, and error information.
    """

    objects = TaskExecutionManager()

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
        db_table = "task_executions"
        verbose_name = "Task Execution"
        verbose_name_plural = "Task Executions"
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

    def get_metrics(self):
        """
        Get associated execution metrics.

        Returns:
            ExecutionMetrics instance if exists, None otherwise
        """
        from apps.trading.models.metrics import ExecutionMetrics

        try:
            # Access the related ExecutionMetrics via the reverse relation
            return ExecutionMetrics.objects.get(execution=self)
        except ExecutionMetrics.DoesNotExist:
            return None


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
        "trading.TaskExecution",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="result",
        help_text="Associated TaskExecution record (if created)",
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
        OandaAccount,
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
