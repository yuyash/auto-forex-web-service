"""Execution snapshot models."""

from django.db import models

from apps.trading.enums import TaskType
from apps.trading.models.base import UUIDModel


class TaskExecutionSnapshot(UUIDModel):
    """Persisted summary/metrics snapshot for a finished execution."""

    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        db_index=True,
        help_text="Task type for this execution snapshot",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the parent task",
    )
    execution_id = models.UUIDField(
        db_index=True,
        help_text="Execution run UUID",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the execution finished",
    )
    summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Serialized task summary snapshot",
    )
    metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Serialized execution metrics snapshot",
    )
    task_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of task-level settings at execution start (instrument, balance, etc.)",
    )
    strategy_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of StrategyConfiguration at execution start (name, type, parameters)",
    )

    class Meta:
        db_table = "task_execution_snapshots"
        verbose_name = "Task Execution Snapshot"
        verbose_name_plural = "Task Execution Snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_id"],
                name="uniq_task_execution_snapshot",
            )
        ]
        indexes = [
            models.Index(fields=["task_type", "task_id"]),
            models.Index(fields=["task_type", "task_id", "execution_id"]),
            models.Index(fields=["completed_at"]),
        ]

    def __str__(self) -> str:
        """Return a compact debug label."""
        return f"{self.task_type}:{self.task_id}:{self.execution_id}"
