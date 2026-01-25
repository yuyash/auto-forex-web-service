"""Execution data models for trades and equity tracking."""

from uuid import uuid4

from django.db import models


class Trades(models.Model):
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
            models.Index(fields=["task_type", "task_id", "instrument"]),
            models.Index(fields=["execution_method"]),
        ]

    def __str__(self) -> str:
        return f"{self.direction} {self.units} {self.instrument} @ {self.price} ({self.pnl})"


class Equities(models.Model):
    """
    Equity curve point for task execution.

    Stores balance snapshots at specific timestamps to build equity curve.
    Points are created periodically or when significant balance changes occur.
    Uses polymorphic task reference to support both BacktestTasks and TradingTasks.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this equity point",
    )
    task_type = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this equity point belongs to",
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
        db_table = "equities"
        verbose_name = "Equity"
        verbose_name_plural = "Equities"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "timestamp"]),
            models.Index(fields=["task_type", "task_id", "celery_task_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "celery_task_id", "timestamp"],
                name="unique_task_execution_equity_timestamp",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp.isoformat()}: {self.balance}"
