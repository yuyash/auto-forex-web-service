"""Position models for trade execution."""

from decimal import Decimal
from uuid import uuid4

from django.db import models

from apps.trading.enums import Direction, TaskType


class Position(models.Model):
    """
    Active or historical position from task execution.

    Stores position details including entry/exit prices, PnL, and timestamps.
    Positions are created when trades are opened and updated when closed.

    In Netting Mode: One position per instrument per task (aggregated).
    In Hedging Mode: Multiple independent positions per instrument per task.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this position",
    )
    task_type = models.CharField(
        max_length=32,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this position belongs to",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for tracking which execution run created this position",
    )
    instrument = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Trading instrument (e.g., EUR_USD)",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        help_text="Position direction (LONG/SHORT)",
    )
    units = models.IntegerField(
        help_text="Number of units in position (positive for long, negative for short)",
    )
    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="Average entry price",
    )
    entry_time = models.DateTimeField(
        db_index=True,
        help_text="When the position was opened",
    )
    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Exit price (null if position is still open)",
    )
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the position was closed (null if still open)",
    )
    realized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Realized profit/loss (null if position is still open)",
    )
    is_open = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the position is currently open",
    )
    layer_index = models.IntegerField(
        null=True,
        blank=True,
        help_text="Layer index for Floor strategy (null for other strategies)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated",
    )

    class Meta:
        db_table = "positions"
        verbose_name = "Position"
        verbose_name_plural = "Positions"
        ordering = ["-entry_time"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-entry_time"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id", "-entry_time"]),
            models.Index(fields=["task_type", "task_id", "instrument", "is_open"]),
            models.Index(fields=["is_open", "-entry_time"]),
            models.Index(fields=["instrument", "is_open"]),
        ]

    def __str__(self) -> str:
        status = "OPEN" if self.is_open else "CLOSED"
        pnl = self.realized_pnl if not self.is_open else None
        return f"{status} {self.direction} {self.units} {self.instrument} @ {self.entry_price} (PnL: {pnl})"

    def close(self, exit_price: Decimal, exit_time: models.DateTimeField) -> None:
        """
        Close the position and calculate realized PnL.

        Args:
            exit_price: Price at which position was closed
            exit_time: Timestamp when position was closed
        """
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.is_open = False

        # Calculate realized PnL
        price_diff = exit_price - self.entry_price
        if self.direction == Direction.SHORT:
            price_diff = -price_diff

        self.realized_pnl = price_diff * abs(self.units)
