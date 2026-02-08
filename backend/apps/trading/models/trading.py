"""Trading task model."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import models

from apps.market.models import OandaAccounts
from apps.trading.enums import TaskStatus, TradingMode
from apps.trading.models.base import UUIDModel


class TradingTaskManager(models.Manager["TradingTask"]):
    """Custom manager for TradingTask model."""

    def for_user(self, user: Any) -> models.QuerySet["TradingTask"]:
        """Get trading tasks for a specific user."""
        return self.filter(user=user)

    def active(self) -> models.QuerySet["TradingTask"]:
        """Get all active (running) trading tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def running(self) -> models.QuerySet["TradingTask"]:
        """Get all running trading tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def for_account(self, account: Any) -> models.QuerySet["TradingTask"]:
        """Get trading tasks for a specific OANDA account."""
        return self.filter(oanda_account=account)

    def by_config(self, config: Any) -> models.QuerySet["TradingTask"]:
        """Get trading tasks using a specific strategy configuration."""
        return self.filter(config=config)


class TradingTask(UUIDModel):
    """
    Persistent live trading task with reusable configuration.

    A TradingTask represents a live trading operation with specific configuration
    and account. Tasks can be started, stopped, paused, and resumed multiple times,
    with each execution tracked separately.

    Only one task can be running per account at a time.

    Inherits UUID primary key and timestamps from UUIDModel.
    """

    objects = TradingTaskManager()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="trading_tasks",
        help_text="User who created this trading task",
    )
    config = models.ForeignKey(
        "trading.StrategyConfiguration",
        on_delete=models.PROTECT,
        related_name="trading_tasks",
        help_text="Strategy configuration used by this task",
    )
    oanda_account = models.ForeignKey(
        OandaAccounts,
        on_delete=models.PROTECT,
        related_name="trading_tasks",
        help_text="OANDA account used for trading",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this trading task",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this trading task",
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

    sell_on_stop = models.BooleanField(
        default=False,
        help_text="Close all positions when task is stopped",
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
    strategy_state = models.JSONField(
        default=dict,
        blank=True,
        help_text="Strategy-specific state for persistence across restarts",
    )

    class Meta:
        db_table = "trading_tasks"
        verbose_name = "Trading Task"
        verbose_name_plural = "Trading Tasks"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_trading_task_name",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        TaskStatus.CREATED,
                        TaskStatus.CREATED,
                        TaskStatus.RUNNING,
                        TaskStatus.STOPPED,
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.STOPPED,
                    ]
                ),
                name="valid_trading_task_status",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["oanda_account", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["celery_task_id"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type}) - {self.oanda_account.account_id}"

    @property
    def duration(self) -> timedelta | None:
        """Calculate task execution duration.

        Returns:
            timedelta | None: Duration if both started_at and completed_at are set, None otherwise
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def copy(self, new_name: str) -> "TradingTask":
        """
        Create a copy of this task with a new name.

        All task properties are duplicated except name and ID.

        Args:
            new_name: Name for the new task

        Returns:
            TradingTask: The newly created task

        Raises:
            ValueError: If new_name is the same as current name or already exists
        """
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        # Check if name already exists for this user
        if TradingTask.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A trading task with name '{new_name}' already exists")

        # Create copy
        new_task = TradingTask.objects.create(
            user=self.user,
            config=self.config,
            oanda_account=self.oanda_account,
            name=new_name,
            description=self.description,
            status=TaskStatus.CREATED,
        )

        return new_task

    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:
        """Delete the task.

        Raises:
            ValueError: If task is in an active state (STARTING, RUNNING, STOPPING)
        """
        if self.status in [TaskStatus.STARTING, TaskStatus.RUNNING, TaskStatus.STOPPING]:
            raise ValueError(
                f"Cannot delete task in {self.status} state. Stop the task first before deleting."
            )

        return super().delete(*args, **kwargs)

    def validate_configuration(self) -> tuple[bool, str | None]:
        """
        Validate task configuration before execution.

        Validates:
        - Strategy configuration parameters
        - Account ownership
        - Account is active

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate account ownership
        if self.oanda_account.user != self.user:
            return False, "Account does not belong to the user"

        # Validate account is active
        if not self.oanda_account.is_active:
            return False, "Account is not active"

        # Validate strategy configuration
        is_valid, error_message = self.config.validate_parameters()
        if not is_valid:
            return False, f"Configuration validation failed: {error_message}"

        return True, None

    def has_strategy_state(self) -> bool:
        """Check if task has saved strategy state."""
        return bool(self.strategy_state)

    def can_resume(self) -> bool:
        """Whether a stopped/failed task has enough state to resume."""
        return self.status in [TaskStatus.STOPPED, TaskStatus.FAILED] and self.has_strategy_state()

    @property
    def account_id(self) -> int:
        """Get the OANDA account ID.

        Returns:
            int: The primary key of the associated OANDA account
        """
        return self.oanda_account_id  # type: ignore[return-value]
