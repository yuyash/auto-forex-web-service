"""
Backtesting models for strategy performance evaluation.

This module contains models for:
- Backtest: Backtest configuration and execution tracking
- BacktestResult: Performance metrics and equity curve

Requirements: 12.1, 12.4
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Backtest(models.Model):
    """
    Backtest configuration and execution tracking.

    This model stores backtest configuration including strategy type,
    parameters, instruments, date range, and execution status.

    Requirements: 12.1, 12.4
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("terminated", "Terminated"),  # Terminated due to resource limits
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="backtests",
        help_text="User who created this backtest",
    )
    strategy_type = models.CharField(
        max_length=50,
        help_text="Type of strategy to backtest (e.g., 'floor', 'trend_following')",
    )
    config = models.JSONField(
        default=dict,
        help_text="Strategy configuration parameters",
    )
    instruments = models.JSONField(
        default=list,
        help_text="List of currency pairs to backtest (e.g., ['EUR_USD', 'GBP_USD'])",
    )
    start_date = models.DateTimeField(
        help_text="Start date for backtest period",
    )
    end_date = models.DateTimeField(
        help_text="End date for backtest period",
    )
    initial_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=10000,
        help_text="Initial account balance for backtest",
    )
    slippage_pips = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Slippage in pips to apply to each trade",
    )
    commission_per_trade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Commission to apply per trade",
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=STATUS_CHOICES,
        db_index=True,
        help_text="Current backtest execution status",
    )
    progress = models.IntegerField(
        default=0,
        help_text="Backtest progress percentage (0-100)",
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if backtest failed",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when backtest execution started",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when backtest execution completed",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when backtest was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when backtest was last updated",
    )
    # Resource usage tracking
    peak_memory_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peak memory usage in MB during backtest execution",
    )
    memory_limit_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Memory limit in MB configured for backtest",
    )
    cpu_limit_cores = models.IntegerField(
        null=True,
        blank=True,
        help_text="CPU cores limit configured for backtest",
    )
    total_trades = models.IntegerField(
        default=0,
        help_text="Total number of trades executed in backtest",
    )
    winning_trades = models.IntegerField(
        default=0,
        help_text="Number of winning trades in backtest",
    )
    losing_trades = models.IntegerField(
        default=0,
        help_text="Number of losing trades in backtest",
    )
    total_return = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total return from backtest",
    )
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Win rate as a percentage",
    )
    final_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final balance after backtest",
    )
    equity_curve = models.JSONField(
        default=list,
        help_text="Equity curve data",
    )
    trade_log = models.JSONField(
        default=list,
        help_text="Trade log data",
    )

    class Meta:
        db_table = "backtests"
        verbose_name = "Backtest"
        verbose_name_plural = "Backtests"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["strategy_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.strategy_type} backtest by {self.user.email} - {self.status}"

    def start(self) -> None:
        """Mark backtest as running."""
        self.status = "running"
        self.started_at = timezone.now()
        self.progress = 0
        self.save(update_fields=["status", "started_at", "progress", "updated_at"])

    def update_progress(self, progress: int) -> None:
        """
        Update backtest progress.

        Args:
            progress: Progress percentage (0-100)
        """
        self.progress = max(0, min(100, progress))
        self.save(update_fields=["progress", "updated_at"])

    def complete(self) -> None:
        """Mark backtest as completed."""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.progress = 100
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "progress",
                "updated_at",
            ]
        )

    def fail(self, error_message: str) -> None:
        """
        Mark backtest as failed.

        Args:
            error_message: Error message describing the failure
        """
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "error_message",
                "completed_at",
                "updated_at",
            ]
        )

    def cancel(self) -> None:
        """Mark backtest as cancelled."""
        self.status = "cancelled"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    @property
    def duration(self) -> str:
        """
        Calculate backtest execution duration.

        Returns:
            Duration as a formatted string
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            seconds = delta.total_seconds()
            if seconds < 60:
                return f"{seconds:.0f}s"
            minutes = seconds / 60
            if minutes < 60:
                return f"{minutes:.1f}m"
            hours = minutes / 60
            return f"{hours:.1f}h"
        return "N/A"

    @property
    def is_running(self) -> bool:
        """Check if backtest is currently running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if backtest has completed successfully."""
        return self.status == "completed"


class BacktestResult(models.Model):  # pylint: disable=too-many-instance-attributes
    """
    Backtest performance metrics and equity curve.

    This model stores the results of a completed backtest including
    performance metrics, trade statistics, and equity curve data.

    Requirements: 12.4
    """

    backtest = models.OneToOneField(
        Backtest,
        on_delete=models.CASCADE,
        related_name="result",
        help_text="Backtest associated with these results",
    )
    final_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Final account balance after backtest",
    )
    total_return = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Total return as a percentage",
    )
    total_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Total profit/loss",
    )
    max_drawdown = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Maximum drawdown as a percentage",
    )
    max_drawdown_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Maximum drawdown in currency units",
    )
    sharpe_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Sharpe ratio (risk-adjusted return)",
    )
    total_trades = models.IntegerField(
        default=0,
        help_text="Total number of trades executed",
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
        help_text="Win rate as a percentage",
    )
    average_win = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Average profit per winning trade",
    )
    average_loss = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Average loss per losing trade",
    )
    largest_win = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Largest winning trade",
    )
    largest_loss = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Largest losing trade",
    )
    profit_factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Profit factor (gross profit / gross loss)",
    )
    average_trade_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Average duration of trades",
    )
    equity_curve = models.JSONField(
        default=list,
        help_text="Equity curve data as list of {timestamp, balance} objects",
    )
    trade_log = models.JSONField(
        default=list,
        help_text="Detailed trade log as list of trade objects",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when results were created",
    )

    class Meta:
        db_table = "backtest_results"
        verbose_name = "Backtest Result"
        verbose_name_plural = "Backtest Results"

    def __str__(self) -> str:
        return f"Results for {self.backtest.strategy_type} - " f"Return: {self.total_return}%"

    def calculate_metrics(
        self,
        trades: list[dict],
        equity_curve: list[dict],
        initial_balance: Decimal,
    ) -> None:
        """
        Calculate all performance metrics from trade data.

        Args:
            trades: List of trade dictionaries
            equity_curve: List of equity curve points
            initial_balance: Initial account balance
        """
        self.trade_log = trades
        self.equity_curve = equity_curve

        if not trades:
            self._set_zero_metrics(initial_balance)
            return

        # Calculate basic metrics
        self.total_trades = len(trades)
        self.final_balance = (
            Decimal(str(equity_curve[-1]["balance"])) if equity_curve else initial_balance
        )

        # Calculate P&L
        self.total_pnl = self.final_balance - initial_balance
        self.total_return = (
            (self.total_pnl / initial_balance) * 100 if initial_balance > 0 else Decimal("0")
        )

        # Calculate win/loss statistics
        winning = [t for t in trades if t.get("pnl", 0) > 0]
        losing = [t for t in trades if t.get("pnl", 0) < 0]

        self.winning_trades = len(winning)
        self.losing_trades = len(losing)
        self.win_rate = (
            (Decimal(self.winning_trades) / Decimal(self.total_trades)) * 100
            if self.total_trades > 0
            else Decimal("0")
        )

        # Calculate average win/loss
        if winning:
            total_wins = sum(Decimal(str(t.get("pnl", 0))) for t in winning)
            self.average_win = total_wins / len(winning)
            self.largest_win = max(Decimal(str(t.get("pnl", 0))) for t in winning)
        else:
            self.average_win = Decimal("0")
            self.largest_win = Decimal("0")

        if losing:
            total_losses = sum(Decimal(str(t.get("pnl", 0))) for t in losing)
            self.average_loss = total_losses / len(losing)
            self.largest_loss = min(Decimal(str(t.get("pnl", 0))) for t in losing)
        else:
            self.average_loss = Decimal("0")
            self.largest_loss = Decimal("0")

        # Calculate profit factor
        if losing:
            gross_profit = sum(Decimal(str(t.get("pnl", 0))) for t in winning)
            gross_loss = abs(sum(Decimal(str(t.get("pnl", 0))) for t in losing))
            if isinstance(gross_loss, Decimal) and gross_loss > Decimal("0"):
                self.profit_factor = gross_profit / gross_loss
            else:
                self.profit_factor = None
        else:
            self.profit_factor = None

        # Calculate maximum drawdown
        self._calculate_max_drawdown(equity_curve, initial_balance)

        # Calculate Sharpe ratio (simplified - assumes daily returns)
        self._calculate_sharpe_ratio(equity_curve)

    def _set_zero_metrics(self, initial_balance: Decimal) -> None:
        """Set all metrics to zero/default values."""
        self.total_trades = 0
        self.final_balance = initial_balance
        self.total_pnl = Decimal("0")
        self.total_return = Decimal("0")
        self.winning_trades = 0
        self.losing_trades = 0
        self.win_rate = Decimal("0")
        self.average_win = Decimal("0")
        self.average_loss = Decimal("0")
        self.largest_win = Decimal("0")
        self.largest_loss = Decimal("0")
        self.profit_factor = None
        self.max_drawdown = Decimal("0")
        self.max_drawdown_amount = Decimal("0")
        self.sharpe_ratio = None

    def _calculate_max_drawdown(self, equity_curve: list[dict], initial_balance: Decimal) -> None:
        """Calculate maximum drawdown from equity curve."""
        if not equity_curve:
            self.max_drawdown = Decimal("0")
            self.max_drawdown_amount = Decimal("0")
            return

        peak = initial_balance
        max_dd = Decimal("0")
        max_dd_amount = Decimal("0")

        for point in equity_curve:
            balance = Decimal(str(point.get("balance", 0)))
            peak = max(peak, balance)

            drawdown = peak - balance
            if drawdown > max_dd_amount:
                max_dd_amount = drawdown
                max_dd = (drawdown / peak) * 100 if peak > 0 else Decimal("0")

        self.max_drawdown = max_dd
        self.max_drawdown_amount = max_dd_amount

    def _calculate_sharpe_ratio(self, equity_curve: list[dict]) -> None:
        """Calculate Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            self.sharpe_ratio = None
            return

        # Calculate daily returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_balance = Decimal(str(equity_curve[i - 1].get("balance", 0)))
            curr_balance = Decimal(str(equity_curve[i].get("balance", 0)))

            if prev_balance > 0:
                daily_return = (curr_balance - prev_balance) / prev_balance
                returns.append(float(daily_return))

        if not returns:
            self.sharpe_ratio = None
            return

        # Calculate mean and standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance**0.5

        # Calculate Sharpe ratio (assuming risk-free rate = 0)
        if std_dev > 0:
            # Annualize (assuming 252 trading days)
            annualized_return = mean_return * 252
            annualized_std = std_dev * (252**0.5)
            self.sharpe_ratio = Decimal(str(annualized_return / annualized_std))
        else:
            self.sharpe_ratio = None


class StrategyComparison(models.Model):
    """
    Model to store strategy comparison requests and results.

    Requirements: 5.1, 5.3, 12.4
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="strategy_comparisons",
    )
    strategy_configs = models.JSONField(
        help_text="List of strategy configurations to compare",
    )
    instruments = models.JSONField(
        help_text="List of currency pairs",
    )
    start_date = models.DateTimeField(
        help_text="Start date for comparison period",
    )
    end_date = models.DateTimeField(
        help_text="End date for comparison period",
    )
    initial_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=10000,
    )
    slippage_pips = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    commission_per_trade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=STATUS_CHOICES,
    )
    results = models.JSONField(
        null=True,
        blank=True,
        help_text="Comparison results including metrics table and equity curves",
    )
    error_message = models.TextField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "strategy_comparisons"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Comparison {self.id} - {self.status}"
