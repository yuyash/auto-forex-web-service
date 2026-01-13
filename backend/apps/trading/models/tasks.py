"""Task models for backtesting and live trading."""

from decimal import Decimal
from typing import Any

from django.db import models
from django.utils import timezone

from apps.market.models import OandaAccount
from apps.trading.enums import DataSource, TaskStatus, TaskType


class BacktestTaskManager(models.Manager["BacktestTask"]):
    """Custom manager for BacktestTask model."""

    def for_user(self, user: Any) -> models.QuerySet["BacktestTask"]:
        """Get backtest tasks for a specific user."""
        return self.filter(user=user)

    def running(self) -> models.QuerySet["BacktestTask"]:
        """Get all running backtest tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["BacktestTask"]:
        """Get all completed backtest tasks."""
        return self.filter(status=TaskStatus.COMPLETED)

    def by_config(self, config: Any) -> models.QuerySet["BacktestTask"]:
        """Get backtest tasks using a specific strategy configuration."""
        return self.filter(config=config)


class BacktestTask(models.Model):
    """
    Persistent backtesting task with reusable configuration.

    A BacktestTask represents a backtesting operation with specific configuration,
    data source, and time range. Tasks can be started, stopped, and rerun multiple
    times, with each execution tracked separately.
    """

    objects = BacktestTaskManager()

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
        "StrategyConfig",
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
    _pip_size = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        default=Decimal("0.01"),
        db_column="pip_size",
        help_text="Pip size for the instrument (e.g., 0.0001 for EUR_USD, 0.01 for USD_JPY). If not provided, will be fetched from OANDA account.",
    )
    status = models.CharField(
        max_length=20,
        default=TaskStatus.CREATED,
        choices=TaskStatus.choices,
        db_index=True,
        help_text="Current task status",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the task was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the task was last updated",
    )

    class Meta:
        db_table = "backtest_tasks"
        verbose_name = "Backtest Task"
        verbose_name_plural = "Backtest Tasks"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_backtest_task_name",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type})"

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate task configuration before execution."""
        if self.end_time <= self.start_time:
            return False, "End time must be after start time"

        is_valid, error_message = self.config.validate_parameters()
        if not is_valid:
            return False, f"Configuration validation failed: {error_message}"

        return True, None

    def start(self) -> None:
        """Mark task as running."""
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def stop(self) -> None:
        """Stop a running backtest task.

        Transitions task to stopped state. The execution state is automatically
        persisted, allowing the task to be resumed later.

        Raises:
            ValueError: If task is not running
        """
        if self.status != TaskStatus.RUNNING:
            raise ValueError("Task is not running")

        self.status = TaskStatus.STOPPED
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as stopped
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.RUNNING:
            from django.utils import timezone

            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])

    def resume(self) -> None:
        """Resume a stopped backtest task.

        Transitions task back to running state. The execution will continue
        from the last persisted state.

        Raises:
            ValueError: If task is not stopped
        """
        if self.status != TaskStatus.STOPPED:
            raise ValueError("Task is not stopped")

        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def restart(self) -> None:
        """Restart the backtest task from the beginning.

        Clears all persisted execution state and starts fresh.
        Task can be in any state (stopped, failed, completed) to be restarted,
        but not running.

        Raises:
            ValueError: If task is currently running
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Cannot restart a task that is currently running. Stop it first.")

        # Clear persisted state by deleting execution snapshots
        latest_execution = self.get_latest_execution()
        if latest_execution:
            # Delete execution snapshots to clear state
            from apps.trading.models import ExecutionSnapshot  # type: ignore[attr-defined]

            ExecutionSnapshot.objects.filter(execution=latest_execution).delete()  # type: ignore[attr-defined]

        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def copy(self, new_name: str) -> "BacktestTask":
        """Create a copy of this backtest task with a new name."""
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        if BacktestTask.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A backtest task with name '{new_name}' already exists")

        return BacktestTask.objects.create(
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

    def get_latest_execution(self) -> Any:
        """Get the most recent execution for this task."""
        from apps.trading.models.execution import TaskExecution

        return (
            TaskExecution.objects.filter(
                task_type=TaskType.BACKTEST,
                task_id=self.pk,
            )
            .order_by("-execution_number")
            .first()
        )

    def get_execution_history(self) -> Any:
        """Get all executions for this task, ordered by execution number."""
        from apps.trading.models.execution import TaskExecution

        return TaskExecution.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=self.pk,
        ).order_by("-execution_number")

    @property
    def pip_size(self) -> Decimal:
        """Get pip_size as Decimal with default value.

        Returns:
            Decimal: Pip size for the instrument, defaults to 0.01 if not set

        Example:
            >>> task = BacktestTask.objects.get(id=1)
            >>> pip_size = task.pip_size  # Always returns Decimal
        """
        if self._pip_size is not None:
            return Decimal(str(self._pip_size))
        return Decimal("0.01")


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


class TradingTask(models.Model):
    """
    Persistent live trading task with reusable configuration.

    A TradingTask represents a live trading operation with specific configuration
    and account. Tasks can be started, stopped, paused, and resumed multiple times,
    with each execution tracked separately.

    Only one task can be running per account at a time.
    """

    objects = TradingTaskManager()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="trading_tasks",
        help_text="User who created this trading task",
    )
    config = models.ForeignKey(
        "trading.StrategyConfig",
        on_delete=models.PROTECT,
        related_name="trading_tasks",
        help_text="Strategy configuration used by this task",
    )
    oanda_account = models.ForeignKey(
        OandaAccount,
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the task was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the task was last updated",
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
    _pip_size = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        default=Decimal("0.01"),
        db_column="pip_size",
        help_text="Pip size for the instrument (e.g., 0.0001 for EUR_USD, 0.01 for USD_JPY). If not provided, will be fetched from OANDA account.",
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
                        TaskStatus.RUNNING,
                        TaskStatus.STOPPED,
                        TaskStatus.FAILED,
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
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type}) - {self.oanda_account.account_id}"

    def start(self) -> None:
        """
        Start the trading task.

        Transitions task to running state. The actual TaskExecution record
        will be created by the Celery task that performs the trading.
        Enforces one active task per account constraint.

        Raises:
            ValueError: If task is already running or another task is running on the account
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(pk=self.pk)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as running
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.STOPPED:
            latest_execution.status = TaskStatus.RUNNING
            latest_execution.save(update_fields=["status"])

    def stop(self) -> None:
        """
        Stop a running trading task.

        Transitions task to stopped state and marks current execution as stopped.
        The execution state is automatically persisted, allowing the task to be
        resumed later.

        Raises:
            ValueError: If task is not running
        """
        if self.status != TaskStatus.RUNNING:
            raise ValueError("Task is not running")

        # Update task status
        self.status = TaskStatus.STOPPED
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as stopped
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.RUNNING:
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])

    def resume(self) -> None:
        """
        Resume a stopped trading task.

        Transitions task back to running state. The execution will continue
        from the last persisted state.

        Raises:
            ValueError: If task is not stopped or another task is running on the account
        """
        if self.status != TaskStatus.STOPPED:
            raise ValueError("Task is not stopped")

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(pk=self.pk)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as running
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.STOPPED:
            latest_execution.status = TaskStatus.RUNNING
            latest_execution.save(update_fields=["status"])

    def restart(self, *, clear_state: bool = True) -> None:
        """Restart task from the beginning.

        Clears all persisted execution state and starts fresh.
        Task can be in any state (stopped, failed) to be restarted, but not running.

        Args:
            clear_state: Whether to clear persisted strategy state (default: True)

        Raises:
            ValueError: If task is currently running or another task is running on the account
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Cannot restart a task that is currently running. Stop it first.")

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(pk=self.pk)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        if clear_state:
            self.strategy_state = {}

            # Clear persisted state by deleting execution snapshots
            latest_execution = self.get_latest_execution()
            if latest_execution:
                # Delete execution snapshots to clear state
                from apps.trading.models import ExecutionSnapshot  # type: ignore[attr-defined]

                ExecutionSnapshot.objects.filter(execution=latest_execution).delete()  # type: ignore[attr-defined]

        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "strategy_state", "updated_at"])

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

    def get_latest_execution(self) -> Any:
        """Get the most recent execution for this task."""
        from apps.trading.models.execution import TaskExecution

        return (
            TaskExecution.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.pk,
            )
            .order_by("-execution_number")
            .first()
        )

    def get_execution_history(self) -> Any:
        """Get all executions for this task, ordered by execution number."""
        from apps.trading.models.execution import TaskExecution

        return TaskExecution.objects.filter(
            task_type=TaskType.TRADING,
            task_id=self.pk,
        ).order_by("-execution_number")

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
    def pip_size(self) -> Decimal:
        """Get pip_size as Decimal with default value.

        Returns:
            Decimal: Pip size for the instrument, defaults to 0.01 if not set

        Example:
            >>> task = TradingTask.objects.get(id=1)
            >>> pip_size = task.pip_size  # Always returns Decimal
        """
        if self._pip_size is not None:
            return Decimal(str(self._pip_size))
        return Decimal("0.01")


class FloorSide(models.TextChoices):
    """Side used by the floor strategy for layering."""

    LONG = "long", "Long"
    SHORT = "short", "Short"
