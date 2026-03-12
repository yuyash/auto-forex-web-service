"""Metrics model for time-series strategy metrics."""

from uuid import uuid4

from django.db import models


class Metrics(models.Model):
    """
    Time-series metric recorded during strategy execution.

    Stores strategy-specific metrics as a JSON field, aggregated at
    minute-level granularity by MetricsAggregator.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    task_type = models.CharField(max_length=32)
    task_id = models.UUIDField()
    execution_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Execution run UUID (shared with Celery task_id)",
    )
    timestamp = models.DateTimeField()
    metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Strategy-specific metrics as JSON",
    )

    class Meta:
        db_table = "metrics"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "execution_id", "timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_id", "timestamp"],
                name="unique_metric_timestamp_per_run",
            ),
        ]

    def __str__(self) -> str:
        return f"Metrics({self.timestamp})"
