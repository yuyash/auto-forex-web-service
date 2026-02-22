"""Event and log models for trading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from apps.trading.dataclasses.context import EventContext
    from apps.trading.events.base import StrategyEvent


class TradingEvent(models.Model):
    """Persistent event log for the trading app.

    This is intentionally independent from any market/accounts event mechanisms.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, default="info", db_index=True)
    description = models.TextField()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    account = models.ForeignKey(
        "market.OandaAccounts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    instrument = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    task_type = models.CharField(max_length=32, blank=True, default="", db_index=True)
    task_id = models.UUIDField(null=True, blank=True, db_index=True)
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for tracking specific execution",
    )

    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "trading_events"
        verbose_name = "Trading Events"
        verbose_name_plural = "Trading Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-created_at"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at.isoformat()} [{self.severity}] {self.event_type}"

    @classmethod
    def from_event(
        cls,
        *,
        event: "StrategyEvent",
        context: "EventContext",
        celery_task_id: str | None = None,
    ) -> "TradingEvent":
        """Create a TradingEvent instance from a StrategyEvent.

        Args:
            event: Strategy event to convert
            context: Event context with user, account, instrument, task info
            celery_task_id: Optional Celery task ID

        Returns:
            TradingEvent: New TradingEvent instance (not saved to database)
        """
        return cls(
            task_type=context.task_type.value,
            task_id=context.task_id,
            celery_task_id=celery_task_id,
            event_type=event.event_type,
            severity="info",
            description=str(event.to_dict()),
            user=context.user,
            account=context.account,
            instrument=context.instrument,
            details=event.to_dict(),
        )
