"""
Execution tracking models for task-based strategy configuration.

This module contains models for:
- TaskExecution: Track individual execution runs of tasks
- ExecutionMetrics: Performance metrics for completed executions

Requirements: 4.3, 4.6, 4.8, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

from decimal import Decimal
from typing import Any

from django.db import models
from django.utils import timezone

from .enums import TaskStatus, TaskType


class TaskExecution(models.Model):
    """
    Track individual execution runs of tasks.

    This model records each execution attempt of a backtest or trading task,
    including status, timing, and error information.

    Requirements: 4.3, 4.6, 4.8, 7.3, 7.4, 7.5
    """

    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.IntegerField(
        help_text="ID of the parent task",
    )
    execution_number = models.IntegerField(
        help_text="Sequential execution number for the task",
    )
    status = models.CharField(
        max_length=20,
        default=TaskStatus.CREATED,
        choices=TaskStatus.choices,
        db_index=True,
        help_text="Current execution status",
    )
    progress = models.IntegerField(
        default=0,
        help_text="Execution progress percentage (0-100)",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Execution start timestamp",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Execution completion timestamp",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if execution failed",
    )
    error_traceback = models.TextField(
        blank=True,
        default="",
        help_text="Full traceback for debugging",
    )
    logs = models.JSONField(
        default=list,
        blank=True,
        help_text="Execution logs as list of {timestamp, level, message} objects",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Record creation timestamp",
    )

    class Meta:
        db_table = "task_executions"
        verbose_name = "Task Execution"
        verbose_name_plural = "Task Executions"
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_number"],
                name="unique_task_execution",
            )
        ]
        indexes = [
            models.Index(fields=["task_type", "task_id", "created_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"{self.task_type} Task {self.task_id} - "
            f"Execution #{self.execution_number} ({self.status})"
        )

    def mark_completed(self) -> None:
        """Mark execution as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = timezone.now()
        self.progress = 100
        # Include logs in save to ensure they're persisted
        self.save(update_fields=["status", "completed_at", "progress", "logs"])

    def update_progress(self, progress: int, user_id: int | None = None) -> None:
        """
        Update execution progress.

        Args:
            progress: Progress percentage (0-100)
            user_id: Optional user ID for WebSocket notification
        """
        self.progress = max(0, min(100, progress))
        self.save(update_fields=["progress"])

        # Send real-time progress update via WebSocket if user_id provided
        if user_id is not None:
            from trading.services.notifications import send_execution_progress_notification

            send_execution_progress_notification(
                task_type=self.task_type,
                task_id=self.task_id,
                execution_id=self.id,
                progress=self.progress,
                user_id=user_id,
            )

    def add_log(self, level: str, message: str) -> None:
        """
        Add a log entry to the execution logs.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
        """
        log_entry = {
            "timestamp": timezone.now().isoformat(),
            "level": level,
            "message": message,
        }
        if not isinstance(self.logs, list):
            self.logs = []
        self.logs.append(log_entry)
        self.save(update_fields=["logs"])

        # Send real-time log update via WebSocket
        from trading.services.notifications import send_execution_log_notification

        send_execution_log_notification(
            task_type=self.task_type,
            task_id=self.task_id,
            execution_id=self.id,
            execution_number=self.execution_number,
            log_entry=log_entry,
        )

    def mark_failed(self, error: Exception) -> None:
        """
        Mark execution as failed with error details.

        Args:
            error: Exception that caused the failure
        """
        import traceback

        self.status = TaskStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = str(error)
        self.error_traceback = traceback.format_exc()
        # Include logs in save to ensure they're persisted even on failure
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_traceback", "logs"]
        )

    def get_duration(self) -> str | None:
        """
        Calculate execution duration.

        Returns:
            Duration as a formatted string, or None if not completed
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            total_seconds = delta.total_seconds()

            if total_seconds < 60:
                return f"{total_seconds:.0f}s"
            if total_seconds < 3600:
                minutes = total_seconds / 60
                return f"{minutes:.1f}m"
            if total_seconds < 86400:
                hours = total_seconds / 3600
                return f"{hours:.1f}h"
            days = total_seconds / 86400
            return f"{days:.1f}d"
        return None

    def get_metrics(self) -> "ExecutionMetrics | None":
        """
        Get associated execution metrics.

        Returns:
            ExecutionMetrics instance if exists, None otherwise
        """
        try:
            return self.metrics
        except ExecutionMetrics.DoesNotExist:
            return None


class ExecutionMetrics(models.Model):
    """
    Performance metrics for completed executions.

    This model stores calculated performance metrics for completed task executions,
    including returns, trade statistics, and equity curve data.

    Requirements: 7.1, 7.2, 7.6, 7.7
    """

    execution = models.OneToOneField(
        TaskExecution,
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
            return

        # Calculate basic statistics
        self.total_trades = len(trades)
        self.total_pnl = sum(Decimal(str(trade.get("pnl", 0))) for trade in trades)

        # Calculate return percentage
        if initial_balance > 0:
            self.total_return = (self.total_pnl / initial_balance) * 100
        else:
            self.total_return = Decimal("0")

        # Calculate win/loss statistics
        winning = [t for t in trades if Decimal(str(t.get("pnl", 0))) > 0]
        losing = [t for t in trades if Decimal(str(t.get("pnl", 0))) < 0]

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
            total_wins = sum(Decimal(str(t.get("pnl", 0))) for t in winning)
            self.average_win = total_wins / Decimal(len(winning))
        else:
            self.average_win = Decimal("0")

        if losing:
            total_losses = sum(Decimal(str(t.get("pnl", 0))) for t in losing)
            self.average_loss = total_losses / Decimal(len(losing))
        else:
            self.average_loss = Decimal("0")

        # Calculate profit factor
        gross_profit = sum((Decimal(str(t.get("pnl", 0))) for t in winning), Decimal("0"))
        gross_loss = abs(sum((Decimal(str(t.get("pnl", 0))) for t in losing), Decimal("0")))

        if gross_loss > Decimal("0"):
            self.profit_factor = gross_profit / gross_loss
        else:
            self.profit_factor = None if gross_profit == Decimal("0") else Decimal("999.9999")

        # Calculate equity curve
        balance = initial_balance
        equity_points = [{"timestamp": None, "balance": float(balance)}]

        for trade in trades:
            balance += Decimal(str(trade.get("pnl", 0)))
            equity_points.append(
                {
                    "timestamp": trade.get("exit_time"),
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
            returns = [Decimal(str(t.get("pnl", 0))) for t in trades]
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
