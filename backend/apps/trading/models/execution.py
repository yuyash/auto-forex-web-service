"""Execution data models for trades and equity tracking."""

from uuid import uuid4

from django.db import models


class ExecutionTrade(models.Model):
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
    task = models.ForeignKey(
        "trading.BacktestTasks",
        on_delete=models.CASCADE,
        related_name="trades",
        help_text="Task this trade belongs to",
    )
    direction = models.CharField(
        max_length=10,
        help_text="Trade direction (long/short)",
    )
    units = models.IntegerField(
        help_text="Number of units traded",
    )
    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Entry price",
    )
    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Exit price",
    )
    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Profit/loss in account currency",
    )
    pips = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Profit/loss in pips",
    )
    entry_timestamp = models.DateTimeField(
        help_text="When the position was opened",
    )
    exit_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the position was closed",
    )
    exit_reason = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Reason for exit (take_profit, stop_loss, etc.)",
    )
    layer_number = models.IntegerField(
        default=0,
        help_text="Layer number for multi-layer strategies",
    )

    class Meta:
        db_table = "execution_trades"
        verbose_name = "Execution Trade"
        verbose_name_plural = "Execution Trades"
        ordering = ["entry_timestamp"]
        indexes = [
            models.Index(fields=["task", "entry_timestamp"]),
            models.Index(fields=["task", "exit_timestamp"]),
            models.Index(fields=["task", "direction"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.direction} {self.units} @ {self.entry_price} -> {self.exit_price} ({self.pnl})"
        )


class ExecutionEquity(models.Model):
    """
    Equity curve point for task execution.

    Stores balance snapshots at specific timestamps to build equity curve.
    Points are created periodically or when significant balance changes occur.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this equity point",
    )
    task = models.ForeignKey(
        "trading.BacktestTasks",
        on_delete=models.CASCADE,
        related_name="equity_points",
        help_text="Task this equity point belongs to",
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for this execution",
    )
    timestamp = models.DateTimeField(
        help_text="Timestamp of this equity snapshot",
    )
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Account balance at this timestamp",
    )
    ticks_processed = models.IntegerField(
        default=0,
        help_text="Number of ticks processed at this point",
    )

    class Meta:
        db_table = "execution_equity_points"
        verbose_name = "Execution Equity"
        verbose_name_plural = "Execution Equity"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task", "timestamp"]),
            models.Index(fields=["task", "celery_task_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "celery_task_id", "timestamp"],
                name="unique_task_execution_equity_timestamp",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp.isoformat()}: {self.balance}"
