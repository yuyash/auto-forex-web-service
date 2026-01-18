"""Execution metrics models."""

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    pass


class TradingMetrics(models.Model):
    """
    Per-tick metrics snapshots for executions.

    This model stores a snapshot of trading metrics for each tick processed
    during an execution. Unlike the old ExecutionMetrics model (which was
    immutable and created only on completion), TradingMetrics records are
    created on every tick and are mutable.

    Each record includes:
    - PnL metrics (realized, unrealized, total)
    - Position metrics (open positions, total trades)
    - Tick statistics (min/max/avg for ask/bid/mid prices)
    """

    execution = models.ForeignKey(
        "trading.Executions",
        on_delete=models.CASCADE,
        related_name="trading_metrics",
        help_text="Associated task execution",
    )
    sequence = models.IntegerField(
        help_text="Monotonic sequence number for ordering within execution",
    )
    timestamp = models.DateTimeField(
        help_text="Timestamp of the tick that generated this snapshot",
    )

    # PnL metrics
    realized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Realized profit/loss from closed positions",
    )
    unrealized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Unrealized profit/loss from open positions",
    )
    total_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Total profit/loss (realized + unrealized)",
    )

    # Position metrics
    open_positions = models.IntegerField(
        help_text="Number of open positions at this tick",
    )
    total_trades = models.IntegerField(
        help_text="Total number of trades executed up to this tick",
    )

    # Tick statistics - Ask
    tick_ask_min = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Minimum ask price in this tick",
    )
    tick_ask_max = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Maximum ask price in this tick",
    )
    tick_ask_avg = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Average ask price in this tick",
    )

    # Tick statistics - Bid
    tick_bid_min = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Minimum bid price in this tick",
    )
    tick_bid_max = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Maximum bid price in this tick",
    )
    tick_bid_avg = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Average bid price in this tick",
    )

    # Tick statistics - Mid
    tick_mid_min = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Minimum mid price in this tick",
    )
    tick_mid_max = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Maximum mid price in this tick",
    )
    tick_mid_avg = models.DecimalField(
        max_digits=20,
        decimal_places=5,
        help_text="Average mid price in this tick",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Record creation timestamp",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Record last update timestamp",
    )

    class Meta:
        db_table = "trading_metrics"
        verbose_name = "Trading Metrics"
        verbose_name_plural = "Trading Metrics"
        ordering = ["execution", "sequence"]
        indexes = [
            models.Index(fields=["execution", "sequence"]),
            models.Index(fields=["execution", "timestamp"]),
        ]
        unique_together = [["execution", "sequence"]]

    def __str__(self) -> str:
        exec_id = self.execution_id if hasattr(self, "execution_id") else "?"
        return f"TradingMetrics(execution={exec_id}, sequence={self.sequence})"
