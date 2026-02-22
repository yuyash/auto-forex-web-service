"""OANDA API health status model."""

from django.db import models
from django.utils import timezone


class OandaApiHealthStatus(models.Model):
    """Persisted OANDA API health check results."""

    account = models.ForeignKey(
        "market.OandaAccounts",
        on_delete=models.CASCADE,
        related_name="api_health_statuses",
    )

    is_available = models.BooleanField(default=False, db_index=True)
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "oanda_api_health_statuses"
        verbose_name = "OANDA API Health Status"
        verbose_name_plural = "OANDA API Health Statuses"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["account", "checked_at"]),
            models.Index(fields=["account", "is_available", "checked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.account.account_id} [{self.http_status}] available={self.is_available}"
