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
        null=True,
        blank=True,
        help_text="Trade direction (LONG/SHORT). Null for close-only trades (e.g. take profit).",
    )
    units = models.IntegerField(
        help_text="Number of units traded",
    )
    instrument = models.CharField(
        max_length=32,
        help_text="Trading instrument (e.g., EUR_USD)",
    )
    oanda_trade_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="OANDA trade ID associated with this trade",
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
    retracement_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of retracements in the layer at the time of this trade",
    )
    position = models.ForeignKey(
        "trading.Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
        help_text="Position this trade belongs to",
    )
    order = models.ForeignKey(
        "trading.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
        help_text="Order that resulted in this trade",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated",
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
        direction_str = self.direction or "CLOSE"
        return f"{direction_str} {self.units} {self.instrument} @ {self.price}"
