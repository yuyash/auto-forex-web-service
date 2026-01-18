"""Execution metrics models."""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import models
from django.utils import timezone

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
        "trading.TaskExecution",
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
        return f"TradingMetrics(execution={self.execution_id}, sequence={self.sequence})"


class ExecutionMetricsManager(models.Manager["ExecutionMetrics"]):
    """Custom manager for ExecutionMetrics model."""

    def for_execution(self, execution: Any) -> "ExecutionMetrics | None":
        """Get metrics for a specific execution."""
        return self.filter(execution=execution).first()


class ExecutionMetrics(models.Model):
    """
    Performance metrics

    This model stores calculated performance metrics for completed task executions,
    including returns, trade statistics, and equity curve data.
    """

    objects = ExecutionMetricsManager()

    execution = models.OneToOneField(
        "trading.TaskExecution",
        on_delete=models.CASCADE,
        related_name="metrics",
        help_text="Associated task execution",
    )
    total_return = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total return percentage",
    )
    total_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total profit/loss",
    )
    realized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Realized profit/loss from closed positions",
    )
    unrealized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Unrealized profit/loss from open positions",
    )
    total_trades = models.IntegerField(
        default=0,
        help_text="Number of trades executed",
    )
    winning_trades = models.IntegerField(
        default=0,
        help_text="Number of winning trades",
    )
    losing_trades = models.IntegerField(
        default=0,
        help_text="Number of losing trades",
    )
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Win rate percentage",
    )
    max_drawdown = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Maximum drawdown percentage",
    )
    sharpe_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Sharpe ratio (risk-adjusted return)",
    )
    profit_factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Profit factor (gross profit / gross loss)",
    )
    average_win = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Average profit per winning trade",
    )
    average_loss = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Average loss per losing trade",
    )
    equity_curve = models.JSONField(
        default=list,
        help_text="Array of equity curve data points",
    )
    trade_log = models.JSONField(
        default=list,
        help_text="Array of trade details",
    )
    strategy_events = models.JSONField(
        default=list,
        help_text="Strategy events log (for floor strategy markers and debugging)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Record creation timestamp",
    )

    class Meta:
        db_table = "execution_metrics"
        verbose_name = "Execution Metrics"
        verbose_name_plural = "Execution Metrics"
        indexes = [
            models.Index(fields=["execution"]),
        ]

    def __str__(self) -> str:
        return (
            f"Metrics for Execution #{self.execution.execution_number} - "
            f"Return: {self.total_return}%"
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Override save to make model immutable after creation.

        Raises:
            ValueError: If attempting to update an existing record
        """
        if self.pk is not None:
            # Check if this is an update (record already exists)
            existing = ExecutionMetrics.objects.filter(pk=self.pk).first()
            if existing:
                raise ValueError("ExecutionMetrics cannot be modified after creation")
        super().save(*args, **kwargs)

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def calculate_from_trades(self, trades: list[dict[str, Any]], initial_balance: Decimal) -> None:
        """
        Calculate all metrics from trade data.

        Args:
            trades: List of trade dictionaries with keys: pnl, entry_time, exit_time, etc.
            initial_balance: Starting balance for the execution
        """
        if not trades:
            self.total_trades = 0
            self.winning_trades = 0
            self.losing_trades = 0
            self.win_rate = Decimal("0")
            self.total_pnl = Decimal("0")
            self.total_return = Decimal("0")
            # Still emit a single equity point with a usable timestamp so charts render.
            self.equity_curve = [
                {
                    "timestamp": timezone.now().isoformat(),
                    "balance": float(initial_balance),
                }
            ]
            self.trade_log = []
            return

        def _trade_pnl(t: dict[str, Any]) -> Decimal:
            direct = t.get("pnl")
            if direct is not None:
                return Decimal(str(direct))
            details_raw = t.get("details")
            if isinstance(details_raw, dict) and details_raw.get("pnl") is not None:
                return Decimal(str(details_raw.get("pnl")))
            return Decimal("0")

        # Calculate basic statistics
        self.total_trades = len(trades)
        self.total_pnl = sum((_trade_pnl(trade) for trade in trades), Decimal("0"))

        # Calculate realized P&L (from closed trades with exit_time)
        closed_trades = [t for t in trades if t.get("exit_time")]
        self.realized_pnl = sum((_trade_pnl(t) for t in closed_trades), Decimal("0"))

        # Calculate unrealized P&L (from open positions without exit_time)
        open_trades = [t for t in trades if not t.get("exit_time")]
        self.unrealized_pnl = sum((_trade_pnl(t) for t in open_trades), Decimal("0"))

        # Calculate return percentage
        if initial_balance > 0:
            self.total_return = (self.total_pnl / initial_balance) * 100
        else:
            self.total_return = Decimal("0")

        # Calculate win/loss statistics
        winning = [t for t in trades if _trade_pnl(t) > 0]
        losing = [t for t in trades if _trade_pnl(t) < 0]

        self.winning_trades = len(winning)
        self.losing_trades = len(losing)

        if self.total_trades > 0:
            win_count = Decimal(self.winning_trades)
            total_count = Decimal(self.total_trades)
            self.win_rate = (win_count / total_count) * 100
        else:
            self.win_rate = Decimal("0")

        # Calculate average win/loss
        if winning:
            total_wins = sum((_trade_pnl(t) for t in winning), Decimal("0"))
            self.average_win = total_wins / Decimal(len(winning))
        else:
            self.average_win = Decimal("0")

        if losing:
            total_losses = sum((_trade_pnl(t) for t in losing), Decimal("0"))
            self.average_loss = total_losses / Decimal(len(losing))
        else:
            self.average_loss = Decimal("0")

        # Calculate profit factor
        gross_profit = sum((_trade_pnl(t) for t in winning), Decimal("0"))
        gross_loss = abs(sum((_trade_pnl(t) for t in losing), Decimal("0")))

        if gross_loss > Decimal("0"):
            self.profit_factor = gross_profit / gross_loss
        else:
            self.profit_factor = None if gross_profit == Decimal("0") else Decimal("999.9999")

        # Calculate equity curve.
        # NOTE: The frontend chart expects a valid timestamp; if we store null/None,
        # Recharts will collapse points onto the epoch and it can look like "1 point".
        from django.utils.dateparse import parse_datetime

        def _to_iso(value: Any) -> str | None:
            if value is None:
                return None
            if hasattr(value, "isoformat"):
                try:
                    # `value` is Any and so is `value.isoformat()`. Coerce to `str`
                    # to satisfy type checkers and to guarantee JSON-serializable output.
                    return str(value.isoformat())
                except Exception:  # pylint: disable=broad-exception-caught
                    return str(value)
            return str(value)

        def _pick_initial_ts(trades_list: list[dict[str, Any]]) -> str:
            candidates: list[str] = []
            for t in trades_list:
                for key in ("entry_time", "exit_time", "timestamp"):
                    raw = t.get(key)
                    if raw:
                        candidates.append(str(raw))
            # Use earliest parseable datetime if possible; otherwise just use "now".
            parsed = [parse_datetime(c) for c in candidates]
            parsed_valid = [p for p in parsed if p is not None]
            if parsed_valid:
                return min(parsed_valid).isoformat()
            return timezone.now().isoformat()

        initial_ts = _pick_initial_ts(trades)
        balance = initial_balance
        equity_points = [{"timestamp": initial_ts, "balance": float(balance)}]

        for trade in trades:
            balance += _trade_pnl(trade)
            point_ts = (
                _to_iso(trade.get("exit_time"))
                or _to_iso(trade.get("entry_time"))
                or _to_iso(trade.get("timestamp"))
                or initial_ts
            )
            equity_points.append(
                {
                    "timestamp": point_ts,
                    "balance": float(balance),
                }
            )

        self.equity_curve = equity_points

        # Calculate max drawdown
        peak = initial_balance
        max_dd = Decimal("0")

        for point in equity_points:
            current_balance = Decimal(str(point["balance"]))
            peak = max(peak, current_balance)
            if peak > 0:
                drawdown = ((peak - current_balance) / peak) * 100
            else:
                drawdown = Decimal("0")
            max_dd = max(max_dd, drawdown)

        self.max_drawdown = max_dd

        # Calculate Sharpe ratio (simplified version)
        if len(trades) > 1:
            returns = [_trade_pnl(t) for t in trades]
            mean_return = sum(returns) / Decimal(len(returns))

            # Calculate variance
            squared_diffs = [(r - mean_return) ** 2 for r in returns]
            variance = sum(squared_diffs) / Decimal(len(returns))

            # Calculate standard deviation
            std_dev = Decimal(str(float(variance) ** 0.5))

            if std_dev > 0:
                # Annualized Sharpe ratio (assuming 252 trading days)
                annualization_factor = Decimal(str(252**0.5))
                self.sharpe_ratio = (mean_return / std_dev) * annualization_factor
            else:
                self.sharpe_ratio = None
        else:
            self.sharpe_ratio = None

        # Store trade log
        self.trade_log = trades

    def get_equity_curve_data(self) -> list[dict[str, Any]]:
        """
        Get formatted equity curve data.

        Returns:
            List of equity curve data points
        """
        return self.equity_curve if isinstance(self.equity_curve, list) else []

    def get_trade_summary(self) -> dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": float(self.win_rate),
            "total_return": float(self.total_return),
            "total_pnl": float(self.total_pnl),
            "average_win": float(self.average_win),
            "average_loss": float(self.average_loss),
            "max_drawdown": float(self.max_drawdown),
            "sharpe_ratio": float(self.sharpe_ratio) if self.sharpe_ratio else None,
            "profit_factor": float(self.profit_factor) if self.profit_factor else None,
        }


class ExecutionMetricsCheckpoint(models.Model):
    """Mutable, periodic metrics snapshots during an execution.

    Unlike `ExecutionMetrics` (immutable, completed-only), checkpoints are
    append-only and intended for live UI updates.
    """

    execution = models.ForeignKey(
        "trading.TaskExecution",
        on_delete=models.CASCADE,
        related_name="metrics_checkpoints",
        help_text="Owning task execution",
    )
    processed = models.IntegerField(null=True, blank=True, help_text="Best-effort ticks processed")
    total_return = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_pnl = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    realized_pnl = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unrealized_pnl = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sharpe_ratio = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    profit_factor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    average_win = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "execution_metrics_checkpoints"
        verbose_name = "Execution Metrics Checkpoint"
        verbose_name_plural = "Execution Metrics Checkpoints"
        indexes = [
            models.Index(fields=["execution", "created_at"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"ExecutionMetricsCheckpoint(exec={self.execution_id}, created_at={self.created_at})"  # type: ignore[attr-defined]
