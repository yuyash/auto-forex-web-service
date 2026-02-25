"""Metrics model for time-series strategy metrics."""

from uuid import uuid4

from django.db import models


class Metrics(models.Model):
    """
    Time-series metric recorded during strategy execution.

    Stores strategy-specific metrics as a generic JSON field, allowing
    each strategy to define its own metrics without schema changes.

    For backward compatibility, the legacy Floor strategy fields
    (margin_ratio, current_atr, baseline_atr, volatility_threshold)
    are accessible via the ``metrics`` JSON field.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )
    task_type = models.CharField(max_length=32, db_index=True)
    task_id = models.UUIDField(db_index=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    execution_run_id = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Execution run identifier to isolate metrics per run",
    )
    timestamp = models.DateTimeField()

    # Legacy Floor strategy fields (kept for backward compatibility with
    # existing data; new strategies should use the ``metrics`` JSON field).
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

    # Generic metrics JSON field for any strategy
    metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Strategy-specific metrics as JSON (e.g., RSI, MACD, custom indicators)",
    )

    class Meta:
        db_table = "metrics"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "execution_run_id", "timestamp"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_run_id", "timestamp"],
                name="unique_metric_timestamp_per_run",
            ),
        ]

    def __str__(self) -> str:
        return f"Metrics({self.timestamp}: margin={self.margin_ratio})"
