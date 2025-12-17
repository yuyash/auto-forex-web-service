"""apps.trading.models

Common models for task execution, performance metrics, and system events.

This module contains:
- Django ORM models: TaskExecution, ExecutionMetrics, TradingEvent
"""

from decimal import Decimal
from typing import Any
import traceback

from django.db import models
from django.utils import timezone

from apps.trading.enums import DataSource, TaskStatus, TaskType
from apps.market.models import OandaAccount


class StrategyConfigManager(models.Manager["StrategyConfig"]):
    """Custom manager for StrategyConfig model."""

    def create_for_user(self, user: Any, **kwargs: Any) -> "StrategyConfig":
        return self.create(user=user, **kwargs)

    def for_user(self, user: Any) -> models.QuerySet["StrategyConfig"]:
        return self.filter(user=user)


class StrategyConfig(models.Model):
    """Reusable strategy configuration used by TradingTask and BacktestTask."""

    objects = StrategyConfigManager()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="strategy_configs",
        help_text="User who created this configuration",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this configuration",
    )
    strategy_type = models.CharField(
        max_length=50,
        help_text="Type of strategy (e.g., 'floor', 'ma_crossover', 'rsi')",
    )
    parameters = models.JSONField(
        default=dict,
        help_text="Strategy-specific configuration parameters",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this configuration",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the configuration was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the configuration was last updated",
    )

    class Meta:
        db_table = "strategy_configs"
        verbose_name = "Strategy Configuration"
        verbose_name_plural = "Strategy Configurations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "strategy_type"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_config_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.strategy_type})"

    def is_in_use(self) -> bool:
        return (
            TradingTask.objects.filter(
                config=self,
                status__in=[TaskStatus.RUNNING, TaskStatus.PAUSED],
            ).exists()
            or BacktestTask.objects.filter(
                config=self,
                status__in=[TaskStatus.RUNNING, TaskStatus.PAUSED],
            ).exists()
        )

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate parameters against the strategy registry schema (best-effort)."""
        from apps.trading.services.registry import registry

        if not registry.is_registered(self.strategy_type):
            return False, f"Strategy type '{self.strategy_type}' is not registered"

        if not isinstance(self.parameters, dict):
            return False, "Parameters must be a JSON object"

        return True, None


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

    @property
    def instrument(self) -> str:
        """Best-effort instrument derived from strategy config."""
        params = getattr(self.config, "parameters", None) or {}
        instrument = params.get("instrument")
        return str(instrument) if instrument else "EUR_USD"

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

    def rerun(self) -> None:
        """Rerun the backtest task from the beginning (status -> RUNNING)."""
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")
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
        return TaskExecution.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=self.pk,
        ).order_by("-execution_number")


class TradingTaskManager(models.Manager["TradingTask"]):
    """Custom manager for TradingTask model."""

    def for_user(self, user: Any) -> models.QuerySet["TradingTask"]:
        """Get trading tasks for a specific user."""
        return self.filter(user=user)

    def active(self) -> models.QuerySet["TradingTask"]:
        """Get all active (running or paused) trading tasks."""
        return self.filter(status__in=[TaskStatus.RUNNING, TaskStatus.PAUSED])

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
                        TaskStatus.PAUSED,
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
        ).exclude(id=self.pk)

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
        if latest_execution and latest_execution.status == TaskStatus.PAUSED:
            latest_execution.status = TaskStatus.RUNNING
            latest_execution.save(update_fields=["status"])

    def stop(self) -> None:
        """
        Stop a running trading task.

        Transitions task to stopped state and marks current execution as stopped.

        Raises:
            ValueError: If task is not running or paused
        """
        if self.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            raise ValueError("Task is not running or paused")

        # Update task status
        self.status = TaskStatus.STOPPED
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as stopped
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])

    def pause(self) -> None:
        """
        Pause a running trading task.

        Transitions task to paused state. Execution continues to track but strategy
        stops making new trades.

        Raises:
            ValueError: If task is not running
        """
        if self.status != TaskStatus.RUNNING:
            raise ValueError("Task is not running")

        # Update task status
        self.status = TaskStatus.PAUSED
        self.save(update_fields=["status", "updated_at"])

        # Mark current execution as paused
        latest_execution = self.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.RUNNING:
            latest_execution.status = TaskStatus.PAUSED
            latest_execution.save(update_fields=["status"])

    def resume(self) -> None:
        """
        Resume a paused trading task.

        Transitions task back to running state.

        Raises:
            ValueError: If task is not paused
        """
        if self.status != TaskStatus.PAUSED:
            raise ValueError("Task is not paused")

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(id=self.pk)

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
        if latest_execution and latest_execution.status == TaskStatus.PAUSED:
            latest_execution.status = TaskStatus.RUNNING
            latest_execution.save(update_fields=["status"])

    def rerun(self) -> None:
        """
        Rerun the trading task from the beginning.

        Transitions task to running state. The actual TaskExecution record
        will be created by the Celery task that performs the trading.
        Task can be in any state (stopped, failed) to be rerun, but not running or paused.

        Raises:
            ValueError: If task is currently running or paused
        """
        if self.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            raise ValueError(
                "Cannot rerun a task that is currently running or paused. Stop it first."
            )

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(id=self.pk)

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

    def restart(self, *, clear_state: bool = True) -> None:
        """Restart task, optionally clearing persisted strategy state."""
        if self.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            raise ValueError(
                "Cannot restart a task that is currently running or paused. Stop it first."
            )

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(id=self.pk)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        if clear_state:
            self.strategy_state = {}

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
        return (
            self.status in [TaskStatus.STOPPED, TaskStatus.FAILED, TaskStatus.CREATED]
            and self.has_strategy_state()
        )


class FloorSide(models.TextChoices):
    """Side used by the floor strategy for layering."""

    LONG = "long", "Long"
    SHORT = "short", "Short"


class FloorStrategyTaskState(models.Model):
    """Persisted floor strategy state for a task (trading or backtest).

    This model exists to persist strategy state across Celery restarts and task
    lifecycle operations without relying on JSON/dict blobs.
    """

    trading_task = models.OneToOneField(
        "trading.TradingTask",
        on_delete=models.CASCADE,
        related_name="floor_state",
        null=True,
        blank=True,
        help_text="Associated live trading task (if applicable)",
    )
    backtest_task = models.OneToOneField(
        "trading.BacktestTask",
        on_delete=models.CASCADE,
        related_name="floor_state",
        null=True,
        blank=True,
        help_text="Associated backtest task (if applicable)",
    )

    status = models.CharField(
        max_length=20,
        default=TaskStatus.CREATED,
        choices=TaskStatus.choices,
        db_index=True,
        help_text="Persisted strategy lifecycle status",
    )
    side = models.CharField(
        max_length=10,
        choices=FloorSide.choices,
        null=True,
        blank=True,
        help_text="Current floor strategy side (long/short)",
    )
    reference_price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Reference price used to build/anchor floor layers",
    )
    last_tick_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last processed tick (best-effort)",
    )

    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "floor_strategy_task_states"
        verbose_name = "Floor Strategy Task State"
        verbose_name_plural = "Floor Strategy Task States"
        constraints = [
            models.CheckConstraint(
                name="floor_state_exactly_one_task",
                condition=(
                    (models.Q(trading_task__isnull=False) & models.Q(backtest_task__isnull=True))
                    | (models.Q(trading_task__isnull=True) & models.Q(backtest_task__isnull=False))
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["status", "updated_at"]),
        ]

    def __str__(self) -> str:
        task = self.trading_task or self.backtest_task
        task_name = getattr(task, "name", "<unknown>")
        return f"FloorState({task_name}) - {self.status}"


class FloorStrategyLayerState(models.Model):
    """Persisted per-layer state for the floor strategy."""

    floor_state = models.ForeignKey(
        "trading.FloorStrategyTaskState",
        on_delete=models.CASCADE,
        related_name="layers",
        help_text="Owning floor strategy task state",
    )

    layer_index = models.PositiveIntegerField(help_text="0-based layer index")
    is_open = models.BooleanField(default=False)

    entry_price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Price where this layer was opened",
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Price where this layer was closed",
    )
    units = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Units allocated to this layer",
    )
    realized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Realized P&L when the layer is closed",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "floor_strategy_layer_states"
        verbose_name = "Floor Strategy Layer State"
        verbose_name_plural = "Floor Strategy Layer States"
        constraints = [
            models.UniqueConstraint(
                fields=["floor_state", "layer_index"],
                name="unique_floor_layer_per_state",
            )
        ]
        indexes = [
            models.Index(fields=["floor_state", "is_open"]),
        ]

    def __str__(self) -> str:
        floor_state_id = getattr(self, "floor_state_id", None)
        return f"FloorLayer(state={floor_state_id}, idx={self.layer_index}, open={self.is_open})"


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
            return

        # Calculate basic statistics
        self.total_trades = len(trades)
        self.total_pnl = sum(Decimal(str(trade.get("pnl", 0))) for trade in trades)

        # Calculate realized P&L (from closed trades with exit_time)
        closed_trades = [t for t in trades if t.get("exit_time")]
        self.realized_pnl = sum(Decimal(str(t.get("pnl", 0))) for t in closed_trades)

        # Calculate unrealized P&L (from open positions without exit_time)
        open_trades = [t for t in trades if not t.get("exit_time")]
        self.unrealized_pnl = sum(Decimal(str(t.get("pnl", 0))) for t in open_trades)

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


class TaskExecutionManager(models.Manager["TaskExecution"]):
    """Custom manager for TaskExecution model."""

    def for_task(self, task_type: str, task_id: int) -> models.QuerySet["TaskExecution"]:
        """Get all executions for a specific task."""
        return self.filter(task_type=task_type, task_id=task_id)

    def running(self) -> models.QuerySet["TaskExecution"]:
        """Get all running executions."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["TaskExecution"]:
        """Get all completed executions."""
        return self.filter(status=TaskStatus.COMPLETED)

    def failed(self) -> models.QuerySet["TaskExecution"]:
        """Get all failed executions."""
        return self.filter(status=TaskStatus.FAILED)


class TaskExecution(models.Model):
    """
    Track individual execution runs of tasks.

    This model records each execution attempt of a backtest or trading task,
    including status, timing, and error information.
    """

    objects = TaskExecutionManager()

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
    cpu_limit_cores = models.IntegerField(
        null=True,
        blank=True,
        help_text="CPU cores limit configured for execution",
    )
    memory_limit_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Memory limit in MB configured for execution",
    )
    peak_memory_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peak memory usage in MB during execution",
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

    def update_progress(self, progress: int) -> None:
        """
        Update execution progress.

        Args:
            progress: Progress percentage (0-100)
        """
        self.progress = max(0, min(100, progress))
        self.save(update_fields=["progress"])

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

    def mark_failed(self, error: Exception) -> None:
        """
        Mark execution as failed with error details.

        Args:
            error: Exception that caused the failure
        """
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
            # Access the related ExecutionMetrics via the reverse relation
            return ExecutionMetrics.objects.get(execution=self)
        except ExecutionMetrics.DoesNotExist:
            return None


class TaskExecutionResult(models.Model):
    """Persistent summary of an execution attempt."""

    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.IntegerField(
        db_index=True,
        help_text="ID of the task that was executed (matches TaskExecution.task_id)",
    )
    execution = models.OneToOneField(
        "trading.TaskExecution",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="result",
        help_text="Associated TaskExecution record (if created)",
    )
    success = models.BooleanField(
        default=False,
        help_text="Whether execution completed successfully",
    )
    error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if failed",
    )
    account = models.ForeignKey(
        OandaAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_execution_results",
        help_text="OANDA account used (for trading tasks)",
    )
    oanda_account_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="OANDA account ID string (for trading tasks)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the result record was created",
    )

    class Meta:
        db_table = "task_execution_results"
        verbose_name = "Task Execution Result"
        verbose_name_plural = "Task Execution Results"
        indexes = [
            models.Index(fields=["task_type", "task_id", "created_at"]),
            models.Index(fields=["success"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.task_type} Task {self.task_id} - {'success' if self.success else 'failed'}"


class CeleryTaskStatus(models.Model):
    """Track a Celery task instance managed by the trading app.

    Long-running tasks should heartbeat and periodically check status to support
    clean shutdowns (e.g., when a cancellation signal is received).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOP_REQUESTED = "stop_requested", "Stop Requested"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Celery task name (e.g. "trading.tasks.run_trading_task")
    task_name = models.CharField(max_length=200, db_index=True)

    # Instance key differentiates multiple runs/instances of the same task.
    instance_key = models.CharField(
        max_length=200,
        blank=True,
        default="default",
        db_index=True,
    )

    celery_task_id = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    worker = models.CharField(max_length=200, null=True, blank=True)

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )

    status_message = models.TextField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "trading_celery_tasks"
        verbose_name = "Trading Celery Task Status"
        verbose_name_plural = "Trading Celery Task Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["task_name", "instance_key"],
                name="uniq_trading_task_name_instance_key",
            )
        ]
        indexes = [
            models.Index(fields=["task_name", "status"], name="tcs_tn_st_idx"),
            models.Index(fields=["celery_task_id"], name="tcs_celery_id_idx"),
            models.Index(fields=["last_heartbeat_at"], name="tcs_hb_idx"),
        ]

    def __str__(self) -> str:
        key = self.instance_key or "default"
        return f"{self.task_name} ({key}) [{self.status}]"


class TradingEvent(models.Model):
    """Persistent event log for the trading app.

    This is intentionally independent from any market/accounts event mechanisms.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, default="info", db_index=True)
    description = models.TextField()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    account = models.ForeignKey(
        "market.OandaAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    instrument = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    task_type = models.CharField(max_length=32, blank=True, default="", db_index=True)
    task_id = models.IntegerField(null=True, blank=True, db_index=True)
    execution = models.ForeignKey(
        "trading.TaskExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )

    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "trading_events"
        verbose_name = "Trading Event"
        verbose_name_plural = "Trading Events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at.isoformat()} [{self.severity}] {self.event_type}"
