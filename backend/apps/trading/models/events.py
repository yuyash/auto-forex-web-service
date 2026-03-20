"""Event and log models for trading."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import models

if TYPE_CHECKING:
    from apps.trading.dataclasses.context import EventContext
    from apps.trading.events.base import StrategyEvent


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _as_datetime(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _as_uuid(value: object) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


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
    strategy_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    visual_group_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    root_entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    parent_entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    basket = models.CharField(max_length=32, blank=True, default="", db_index=True)
    step = models.IntegerField(null=True, blank=True)
    close_reason = models.CharField(max_length=64, blank=True, default="", db_index=True)
    position_id = models.UUIDField(null=True, blank=True, db_index=True)
    direction = models.CharField(max_length=16, blank=True, default="", db_index=True)
    event_timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    expected_interval_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    actual_interval_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    expected_tp_pips = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    actual_tp_pips = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    expected_exit_price = models.DecimalField(
        max_digits=20, decimal_places=10, null=True, blank=True
    )
    actual_exit_price = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    validation_tolerance_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    validation_status = models.CharField(max_length=32, blank=True, default="", db_index=True)

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
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "strategy_type",
                    "-event_timestamp",
                ]
            ),
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "visual_group_id",
                    "event_timestamp",
                ]
            ),
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
        strategy_type: str = "",
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
            strategy_type=str(strategy_type or getattr(event, "strategy_type", "") or ""),
            visual_group_id=str(getattr(event, "visual_group_id", "") or ""),
            root_entry_id=_as_int(getattr(event, "root_entry_id", None)),
            parent_entry_id=_as_int(getattr(event, "parent_entry_id", None)),
            entry_id=_as_int(getattr(event, "entry_id", None)),
            basket=str(getattr(event, "basket", "") or ""),
            step=_as_int(getattr(event, "step", None)),
            close_reason=str(getattr(event, "close_reason", "") or ""),
            position_id=_as_uuid(getattr(event, "position_id", None)),
            direction=str(getattr(event, "direction", "") or ""),
            event_timestamp=_as_datetime(getattr(event, "timestamp", None)),
            expected_interval_pips=_as_decimal(getattr(event, "expected_interval_pips", None)),
            actual_interval_pips=_as_decimal(getattr(event, "actual_interval_pips", None)),
            expected_tp_pips=_as_decimal(getattr(event, "expected_tp_pips", None)),
            actual_tp_pips=_as_decimal(getattr(event, "actual_tp_pips", None)),
            expected_exit_price=_as_decimal(getattr(event, "expected_exit_price", None)),
            actual_exit_price=_as_decimal(getattr(event, "actual_exit_price", None)),
            validation_tolerance_pips=_as_decimal(
                getattr(event, "validation_tolerance_pips", None)
            ),
            validation_status=str(getattr(event, "validation_status", "") or ""),
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
    strategy_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    visual_group_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    root_entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    parent_entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    entry_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    basket = models.CharField(max_length=32, blank=True, default="", db_index=True)
    step = models.IntegerField(null=True, blank=True)
    close_reason = models.CharField(max_length=64, blank=True, default="", db_index=True)
    position_id = models.UUIDField(null=True, blank=True, db_index=True)
    direction = models.CharField(max_length=16, blank=True, default="", db_index=True)
    event_timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    expected_interval_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    actual_interval_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    expected_tp_pips = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    actual_tp_pips = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    expected_exit_price = models.DecimalField(
        max_digits=20, decimal_places=10, null=True, blank=True
    )
    actual_exit_price = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    validation_tolerance_pips = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    validation_status = models.CharField(max_length=32, blank=True, default="", db_index=True)

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
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "strategy_type",
                    "-event_timestamp",
                ]
            ),
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "visual_group_id",
                    "event_timestamp",
                ]
            ),
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "root_entry_id",
                    "event_timestamp",
                ]
            ),
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
        strategy_type: str = "",
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
            strategy_type=str(strategy_type or getattr(event, "strategy_type", "") or ""),
            visual_group_id=str(getattr(event, "visual_group_id", "") or ""),
            root_entry_id=_as_int(getattr(event, "root_entry_id", None)),
            parent_entry_id=_as_int(getattr(event, "parent_entry_id", None)),
            entry_id=_as_int(getattr(event, "entry_id", None)),
            basket=str(getattr(event, "basket", "") or ""),
            step=_as_int(getattr(event, "step", None)),
            close_reason=str(getattr(event, "close_reason", "") or ""),
            position_id=_as_uuid(getattr(event, "position_id", None)),
            direction=str(getattr(event, "direction", "") or ""),
            event_timestamp=_as_datetime(getattr(event, "timestamp", None)),
            expected_interval_pips=_as_decimal(getattr(event, "expected_interval_pips", None)),
            actual_interval_pips=_as_decimal(getattr(event, "actual_interval_pips", None)),
            expected_tp_pips=_as_decimal(getattr(event, "expected_tp_pips", None)),
            actual_tp_pips=_as_decimal(getattr(event, "actual_tp_pips", None)),
            expected_exit_price=_as_decimal(getattr(event, "expected_exit_price", None)),
            actual_exit_price=_as_decimal(getattr(event, "actual_exit_price", None)),
            validation_tolerance_pips=_as_decimal(
                getattr(event, "validation_tolerance_pips", None)
            ),
            validation_status=str(getattr(event, "validation_status", "") or ""),
            details=event.to_dict(),
        )
