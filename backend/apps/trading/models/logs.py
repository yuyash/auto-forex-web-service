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

    Uses polymorphic task reference to support both BacktestTask and TradingTask.
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
    component = models.CharField(
        max_length=255,
        default="unknown",
        db_index=True,
        help_text="Component/logger name that emitted this log",
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
            models.Index(fields=["task_type", "task_id", "component"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self) -> str:
        return f"[{self.level}] {self.task_type}:{self.task_id} @ {self.timestamp.isoformat()}: {self.message[:50]}"
