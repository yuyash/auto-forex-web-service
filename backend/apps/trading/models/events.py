"""Event and log models for trading."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

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
    execution_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Execution run UUID (shared with Celery task_id)",
    )

    details = models.JSONField(default=dict, blank=True)
    is_processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event has been fully executed by the event handler",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when event execution was completed",
    )
    processing_error = models.TextField(
        blank=True,
        default="",
        help_text="Last processing error for retry diagnostics",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "trading_events"
        verbose_name = "Trading Events"
        verbose_name_plural = "Trading Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-created_at"]),
            models.Index(fields=["task_type", "task_id", "execution_id", "-created_at"]),
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
        execution_id: UUID | str | None = None,
    ) -> "TradingEvent":
        """Create a TradingEvent instance from a StrategyEvent.

        Args:
            event: Strategy event to convert
            context: Event context with user, account, instrument, task info
            execution_id: Execution run UUID

        Returns:
            TradingEvent: New TradingEvent instance (not saved to database)
        """
        return cls(
            task_type=context.task_type.value,
            task_id=context.task_id,
            execution_id=execution_id,
            event_type=event.event_type,
            severity="info",
            description=str(event.to_dict()),
            user=context.user,
            account=context.account,
            instrument=context.instrument,
            details=event.to_dict(),
        )


class StrategyEventRecord(models.Model):
    """Persistent log for strategy-internal events.

    These events are emitted by strategies for visualization/diagnostics and are
    intentionally decoupled from order execution in EventHandler.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, default="info", db_index=True)
    description = models.TextField()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_events",
    )
    account = models.ForeignKey(
        "market.OandaAccounts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_events",
    )
    instrument = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    task_type = models.CharField(max_length=32, blank=True, default="", db_index=True)
    task_id = models.UUIDField(null=True, blank=True, db_index=True)
    execution_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Execution run UUID (shared with Celery task_id)",
    )

    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "strategy_events"
        verbose_name = "Strategy Event"
        verbose_name_plural = "Strategy Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-created_at"]),
            models.Index(fields=["task_type", "task_id", "execution_id", "-created_at"]),
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
        execution_id: UUID | str | None = None,
    ) -> "StrategyEventRecord":
        """Create a StrategyEventRecord from a StrategyEvent."""
        return cls(
            task_type=context.task_type.value,
            task_id=context.task_id,
            execution_id=execution_id,
            event_type=event.event_type,
            severity="info",
            description=str(event.to_dict()),
            user=context.user,
            account=context.account,
            instrument=context.instrument,
            details=event.to_dict(),
        )
