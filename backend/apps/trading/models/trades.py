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
    execution_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Execution run UUID (shared with Celery task_id)",
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="When the trade was executed",
    )
    direction = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Trade direction (LONG/SHORT). Matches the original position direction for close trades.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Strategy reasoning for this trade (e.g. layer 1 take profit, retracement entry)",
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
        help_text="Event type that triggered trade (e.g., OPEN_POSITION, CLOSE_POSITION)",
    )
    layer_index = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Strategy-specific layer index for layered strategy trades (1-based: L1, L2, ...)"
        ),
    )
    retracement_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Retracement index at the time of this trade (0-based: R0=initial, R1=first retracement, ...)",
    )
    position = models.ForeignKey(
        "trading.Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
        help_text="Position this trade belongs to",
    )
    cycle_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Cycle identifier grouping all trades from one Initial Entry "
            "through to its close. Equal to the Trade.id of the cycle's "
            "first open trade. NULL for strategies that do not use cycles."
        ),
    )
    order = models.ForeignKey(
        "trading.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
        help_text="Order that resulted in this trade",
    )
    sequence_number = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Monotonically increasing counter within a single tick batch. "
            "Preserves the logical ordering of events that share the same timestamp."
        ),
    )
    margin_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=(
            "Margin closeout ratio at the time this trade was executed. "
            "Stored as a fraction (e.g. 0.791 = 79.1%)."
        ),
    )
    is_rebuild = models.BooleanField(
        default=False,
        help_text="Whether this trade is for a position rebuilt after a stop-loss close.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated",
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this trade was recorded by resumed event replay.",
    )

    class Meta:
        db_table = "trades"
        verbose_name = "Trade"
        verbose_name_plural = "Trades"
        ordering = ["timestamp", "sequence_number"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-timestamp"]),
            models.Index(fields=["task_type", "task_id", "execution_id", "-timestamp"]),
            models.Index(fields=["task_type", "task_id", "instrument"]),
            models.Index(fields=["execution_method"]),
            models.Index(fields=["task_type", "task_id", "cycle_id", "timestamp"]),
        ]

    def __str__(self) -> str:
        direction_str = self.direction or "CLOSE"
        return f"{direction_str} {self.units} {self.instrument} @ {self.price}"
