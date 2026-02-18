"""Trade execution models."""

from uuid import uuid4

from django.db import models


class Trade(models.Model):
    """
    Completed trade from task execution.

    Stores individual trade details including entry/exit prices, PnL,
    and timestamps. Trades are created when positions are closed.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this trade",
    )
    task_type = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this trade belongs to",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for tracking execution run",
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="When the trade was executed",
    )
    direction = models.CharField(
        max_length=10,
        help_text="Trade direction (LONG/SHORT)",
    )
    units = models.IntegerField(
        help_text="Number of units traded",
    )
    instrument = models.CharField(
        max_length=32,
        help_text="Trading instrument (e.g., EUR_USD)",
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="Execution price",
    )
    execution_method = models.CharField(
        max_length=64,
        help_text="Event type that triggered trade (e.g., INITIAL_ENTRY, RETRACEMENT)",
    )
    layer_index = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Layer index for Floor strategy-related trades",
    )
    open_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Entry price when position was opened (populated on close trades)",
    )
    open_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the position was originally opened (populated on close trades)",
    )
    close_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Exit price when position was closed (populated on close trades)",
    )
    close_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the position was closed (populated on close trades)",
    )
    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Profit/loss for this trade (for closes)",
    )

    class Meta:
        db_table = "trades"
        verbose_name = "Trade"
        verbose_name_plural = "Trades"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-timestamp"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id", "-timestamp"]),
            models.Index(fields=["task_type", "task_id", "instrument"]),
            models.Index(fields=["execution_method"]),
        ]

    def __str__(self) -> str:
        return f"{self.direction} {self.units} {self.instrument} @ {self.price} ({self.pnl})"
