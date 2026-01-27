"""Backtest task model."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import models

from apps.trading.enums import DataSource, TaskStatus, TradingMode
from apps.trading.models.base import UUIDModel


class BacktestTasksManager(models.Manager["BacktestTasks"]):
    """Custom manager for BacktestTasks model."""

    def for_user(self, user: Any) -> models.QuerySet["BacktestTasks"]:
        """Get backtest tasks for a specific user."""
        return self.filter(user=user)

    def running(self) -> models.QuerySet["BacktestTasks"]:
        """Get all running backtest tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["BacktestTasks"]:
        """Get all completed backtest tasks."""
        return self.filter(status=TaskStatus.COMPLETED)

    def by_config(self, config: Any) -> models.QuerySet["BacktestTasks"]:
        """Get backtest tasks using a specific strategy configuration."""
        return self.filter(config=config)


class BacktestTasks(UUIDModel):
    """
    Persistent backtesting task with reusable configuration.

    A BacktestTasks represents a backtesting operation with specific configuration,
    data source, and time range. Tasks can be started, stopped, and rerun multiple
    times, with each execution tracked separately.

    Inherits UUID primary key and timestamps from UUIDModel.
    """

    objects = BacktestTasksManager()

    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this backtest task",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this backtest task",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="backtest_tasks",
        help_text="User who created this backtest task",
    )
    config = models.ForeignKey(
        "StrategyConfigurations",
        on_delete=models.PROTECT,
        related_name="backtest_tasks",
        help_text="Strategy configuration used by this task",
    )
    data_source = models.CharField(
        max_length=20,
        choices=DataSource.choices,
        default=DataSource.POSTGRESQL,
        help_text="Data source for historical tick data",
    )
    start_time = models.DateTimeField(
        help_text="Start time for backtest period",
    )
    end_time = models.DateTimeField(
        help_text="End time for backtest period",
    )
    initial_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000"),
        help_text="Initial account balance for backtest",
    )
    commission_per_trade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Commission to apply per trade",
    )
    instrument = models.CharField(
        max_length=20,
        default="USD_JPY",
        help_text="Trading instrument (e.g., EUR_USD, USD_JPY)",
    )
    pip_size = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        default=Decimal("0.01"),
        help_text="Pip size for the instrument (e.g., 0.0001 for EUR_USD, 0.01 for USD_JPY). If not provided, will be fetched from OANDA account.",
    )
    trading_mode = models.CharField(
        max_length=20,
        choices=TradingMode.choices,
        default=TradingMode.NETTING,
        help_text="Trading mode: netting (aggregated positions) or hedging (independent trades)",
    )
    status = models.CharField(
        max_length=20,
        default=TaskStatus.CREATED,
        choices=TaskStatus.choices,
        db_index=True,
        help_text="Current task status",
    )

    # Celery Integration
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Celery task ID for tracking execution",
    )

    # Execution State
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the task execution started",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the task execution completed",
    )

    # Error Tracking
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if task failed",
    )
    error_traceback = models.TextField(
        null=True,
        blank=True,
        help_text="Full error traceback if task failed",
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of times this task has been retried",
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum number of retries allowed",
    )

    class Meta:
        db_table = "backtest_tasks"
        verbose_name = "Backtest Task"
        verbose_name_plural = "Backtest Tasks"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["celery_task_id"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_backtest_task_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type})"

    @property
    def duration(self) -> timedelta | None:
        """Calculate task execution duration.

        Returns:
            timedelta | None: Duration if both started_at and completed_at are set, None otherwise
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate task configuration before execution."""
        if self.end_time <= self.start_time:
            return False, "End time must be after start time"

        is_valid, error_message = self.config.validate_parameters()
        if not is_valid:
            return False, f"Configuration validation failed: {error_message}"

        return True, None

    def copy(self, new_name: str) -> "BacktestTasks":
        """Create a copy of this backtest task with a new name."""
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        if BacktestTasks.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A backtest task with name '{new_name}' already exists")

        return BacktestTasks.objects.create(
            user=self.user,
            config=self.config,
            name=new_name,
            description=self.description,
            data_source=self.data_source,
            start_time=self.start_time,
            end_time=self.end_time,
            initial_balance=self.initial_balance,
            commission_per_trade=self.commission_per_trade,
            status=TaskStatus.CREATED,
        )

    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        """Delete the task.

        Raises:
            ValueError: If task is in an active state (STARTING, RUNNING, STOPPING)
        """
        if self.status in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]:
            raise ValueError(
                f"Cannot delete task in {self.status} state. Stop the task first before deleting."
            )

        return super().delete(*args, **kwargs)
