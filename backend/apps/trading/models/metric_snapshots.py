"""Metric snapshot model for time-series strategy metrics."""

from uuid import uuid4

from django.db import models


class MetricSnapshot(models.Model):
    """
    Time-series metric snapshot recorded during strategy execution.

    Stores margin ratio, volatility data, and other per-tick metrics
    for visualization in the Replay chart.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )
    task_type = models.CharField(max_length=32, db_index=True)
    task_id = models.UUIDField(db_index=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    timestamp = models.DateTimeField()
    margin_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Required margin / NAV",
    )
    current_atr = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Current ATR in pips",
    )
    baseline_atr = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Baseline ATR in pips",
    )
    volatility_threshold = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="baseline_atr * volatility_lock_multiplier",
    )

    class Meta:
        db_table = "metric_snapshots"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "timestamp"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "celery_task_id", "timestamp"],
                name="unique_metric_snapshot_timestamp",
            ),
        ]

    def __str__(self) -> str:
        return f"MetricSnapshot({self.timestamp}: margin={self.margin_ratio})"
