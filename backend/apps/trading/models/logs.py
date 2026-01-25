"""Task execution log and metric models."""

from uuid import uuid4

from django.db import models

from apps.trading.enums import LogLevel, TaskType


class TaskLog(models.Model):
    """
    Execution log entry for a task.

    Stores log messages generated during task execution with timestamp,
    severity level, and message content. Logs are ordered chronologically
    and indexed for efficient querying by task and level.

    Uses polymorphic task reference to support both BacktestTasks and TradingTasks.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this log entry",
    )
    task_type = models.CharField(
        max_length=32,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this log entry belongs to",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for this execution",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this log entry was created",
    )
    level = models.CharField(
        max_length=20,
        choices=LogLevel.choices,
        default=LogLevel.INFO,
        help_text="Log severity level",
    )
    message = models.TextField(
        help_text="Log message content",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured log details",
    )

    class Meta:
        db_table = "task_logs"
        verbose_name = "Task Log"
        verbose_name_plural = "Task Logs"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "timestamp"]),
            models.Index(fields=["task_type", "task_id", "level"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self) -> str:
        return f"[{self.level}] {self.task_type}:{self.task_id} @ {self.timestamp.isoformat()}: {self.message[:50]}"


class TaskMetric(models.Model):
    """
    Execution metric for a task.

    Stores performance metrics and measurements collected during task execution.
    Metrics are time-series data with optional metadata for additional context.
    Indexed for efficient querying by task, metric name, and time range.

    Uses polymorphic task reference to support both BacktestTasks and TradingTasks.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this metric entry",
    )
    task_type = models.CharField(
        max_length=32,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this metric belongs to",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for this execution",
    )
    metric_name = models.CharField(
        max_length=255,
        help_text="Name of the metric (e.g., 'equity', 'drawdown', 'trades_count')",
    )
    metric_value = models.FloatField(
        help_text="Numeric value of the metric",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this metric was recorded",
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional additional metadata for this metric",
    )

    class Meta:
        db_table = "task_metrics"
        verbose_name = "Task Metric"
        verbose_name_plural = "Task Metrics"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "metric_name", "timestamp"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.task_type}:{self.task_id} - {self.metric_name}={self.metric_value} @ {self.timestamp.isoformat()}"
