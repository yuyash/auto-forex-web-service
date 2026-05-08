"""Persisted OANDA retry telemetry models."""

from django.db import models
from django.utils import timezone


class OandaRetryMetric(models.Model):
    """One persisted OANDA retry lifecycle event."""

    namespace = models.CharField(max_length=128, default="oanda_retry_metrics", db_index=True)
    event_name = models.CharField(max_length=32, db_index=True)
    label = models.CharField(max_length=255, blank=True, default="", db_index=True)
    attempts_used = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "oanda_retry_metrics"
        verbose_name = "OANDA Retry Metric"
        verbose_name_plural = "OANDA Retry Metrics"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["namespace", "event_name", "created_at"]),
            models.Index(fields=["namespace", "label", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.namespace}:{self.event_name} label={self.label}"
