"""Task models for backtesting and live trading."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from celery.result import AsyncResult
from django.db import models
from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.trading.enums import DataSource, TaskStatus, TaskType, TradingMode


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


class BacktestTasks(models.Model):
    """
    Persistent backtesting task with reusable configuration.

    A BacktestTasks represents a backtesting operation with specific configuration,
    data source, and time range. Tasks can be started, stopped, and rerun multiple
    times, with each execution tracked separately.
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
    _pip_size = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        default=Decimal("0.01"),
        db_column="pip_size",
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the task was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the task was last updated",
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

    # Results
    result_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Execution results data",
    )
    result_data_external_ref = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Reference to externally stored result data (e.g., fs://path or s3://bucket/key)",
    )

    class Meta:
        db_table = "backtest_tasks"
        verbose_name = "Backtest Task"
        verbose_name_plural = "Backtest Tasks"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["celery_task_id"]),
            models.Index(fields=["status", "created_at"]),
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

    def get_celery_result(self) -> AsyncResult | None:
        """Retrieve the Celery AsyncResult for this task.

        Returns:
            AsyncResult | None: The Celery AsyncResult if celery_task_id is set, None otherwise
        """
        if self.celery_task_id:
            return AsyncResult(self.celery_task_id)
        return None

    def update_from_celery_state(self) -> None:
        """Synchronize task status with Celery task state.

        Maps Celery task states to Task statuses and updates the task accordingly.

        Note: Does not overwrite terminal states (STOPPED, COMPLETED, FAILED, PAUSED) or
        states during transitions (STOP_REQUESTED) to prevent race conditions with async
        stop operations.

        Priority order:
        1. Terminal states - never overwrite
        2. CeleryTaskStatus.STOP_REQUESTED - don't overwrite during stop
        3. CeleryTaskStatus state - use if available
        4. Celery AsyncResult state - fallback
        """
        from apps.trading.services.status_sync import sync_task_status_from_celery

        sync_task_status_from_celery(self, self.get_celery_result())

    def cancel(self) -> bool:
        """Cancel the running task.

        Returns:
            bool: True if task was successfully cancelled, False otherwise
        """
        if self.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            result = self.get_celery_result()
            if result:
                result.revoke(terminate=True)
            self.status = TaskStatus.STOPPED
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at", "updated_at"])
            return True
        return False

    @property
    def duration(self) -> timedelta | None:
        """Calculate task execution duration.

        Returns:
            timedelta | None: Duration if both started_at and completed_at are set, None otherwise
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def set_result_data(self, data: Any) -> None:
        """Set result data, automatically using external storage if needed.

        Args:
            data: Result data to store
        """
        from apps.trading.services.storage import ExternalStorageService

        storage_service = ExternalStorageService()
        inline_data, external_ref = storage_service.store_if_needed(self.pk, data)

        self.result_data = inline_data
        self.result_data_external_ref = external_ref
        self.save(update_fields=["result_data", "result_data_external_ref", "updated_at"])

    def get_result_data(self) -> Any:
        """Get result data from inline or external storage.

        Returns:
            Any: The result data

        Raises:
            FileNotFoundError: If external reference is invalid
        """
        from apps.trading.services.storage import ExternalStorageService

        storage_service = ExternalStorageService()
        return storage_service.retrieve_data(self.result_data, self.result_data_external_ref)

    def clear_result_data(self) -> None:
        """Clear result data from both inline and external storage."""
        from apps.trading.services.storage import ExternalStorageService

        # Delete external data if it exists
        if self.result_data_external_ref:
            storage_service = ExternalStorageService()
            storage_service.delete_external_data(self.result_data_external_ref)

        # Clear both fields
        self.result_data = None
        self.result_data_external_ref = None
        self.save(update_fields=["result_data", "result_data_external_ref", "updated_at"])

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

    def pause(self) -> None:
        """Pause a running backtest task.

        Transitions task to paused state. The execution state is preserved.

        Raises:
            ValueError: If task is not running
        """
        if self.status != TaskStatus.RUNNING:
            raise ValueError("Task is not running")

        self.status = TaskStatus.PAUSED
        self.save(update_fields=["status", "updated_at"])

    def restart(self) -> bool:
        """Restart a task from the beginning, clearing all execution data.

        Returns:
            bool: True if task was successfully restarted, False otherwise

        Raises:
            ValueError: If task is currently running
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Cannot restart a task that is currently running. Stop it first.")

        if self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.STOPPED,
            TaskStatus.STOPPED,
        ]:
            # Clear result data (including external storage)
            self.clear_result_data()

            # Clear all events associated with this task
            from apps.trading.models import TradingEvent

            TradingEvent.objects.filter(task_type="backtest", task_id=self.pk).delete()

            # Clear all other execution data
            self.celery_task_id = None
            self.status = TaskStatus.CREATED
            self.started_at = None
            self.completed_at = None
            self.error_message = None
            self.error_traceback = None
            self.retry_count += 1
            self.save()
            return True
        return False

    def resume(self) -> bool:
        """Resume a paused task, preserving execution context.

        Returns:
            bool: True if task was successfully resumed, False otherwise
        """
        if self.status == TaskStatus.PAUSED:
            # Keep existing execution data, just change status back to running
            self.celery_task_id = None
            self.status = TaskStatus.RUNNING
            self.save()
            return True
        return False

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
        """Delete the task and stop any running Celery tasks."""
        from apps.trading.services.lock import TaskLockManager

        # Stop the Celery task if running
        if self.status == TaskStatus.RUNNING:
            lock_manager = TaskLockManager()
            lock_manager.set_cancellation_flag(TaskType.BACKTEST, self.pk)

        return super().delete(*args, **kwargs)

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


class TradingTasksManager(models.Manager["TradingTasks"]):
    """Custom manager for TradingTasks model."""

    def for_user(self, user: Any) -> models.QuerySet["TradingTasks"]:
        """Get trading tasks for a specific user."""
        return self.filter(user=user)

    def active(self) -> models.QuerySet["TradingTasks"]:
        """Get all active (running) trading tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def running(self) -> models.QuerySet["TradingTasks"]:
        """Get all running trading tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def for_account(self, account: Any) -> models.QuerySet["TradingTasks"]:
        """Get trading tasks for a specific OANDA account."""
        return self.filter(oanda_account=account)

    def by_config(self, config: Any) -> models.QuerySet["TradingTasks"]:
        """Get trading tasks using a specific strategy configuration."""
        return self.filter(config=config)


class TradingTasks(models.Model):
    """
    Persistent live trading task with reusable configuration.

    A TradingTasks represents a live trading operation with specific configuration
    and account. Tasks can be started, stopped, paused, and resumed multiple times,
    with each execution tracked separately.

    Only one task can be running per account at a time.
    """

    objects = TradingTasksManager()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="trading_tasks",
        help_text="User who created this trading task",
    )
    config = models.ForeignKey(
        "trading.StrategyConfigurations",
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the task was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the task was last updated",
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

    # Results
    result_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Execution results data",
    )
    result_data_external_ref = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Reference to externally stored result data (e.g., fs://path or s3://bucket/key)",
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

    def get_celery_result(self) -> AsyncResult | None:
        """Retrieve the Celery AsyncResult for this task.

        Returns:
            AsyncResult | None: The Celery AsyncResult if celery_task_id is set, None otherwise
        """
        if self.celery_task_id:
            return AsyncResult(self.celery_task_id)
        return None

    def update_from_celery_state(self) -> None:
        """Synchronize task status with Celery task state.

        Maps Celery task states to Task statuses and updates the task accordingly.

        Note: Does not overwrite terminal states (STOPPED, COMPLETED, FAILED, PAUSED) or
        states during transitions (STOP_REQUESTED) to prevent race conditions with async
        stop operations.

        Priority order:
        1. Terminal states - never overwrite
        2. CeleryTaskStatus.STOP_REQUESTED - don't overwrite during stop
        3. CeleryTaskStatus state - use if available
        4. Celery AsyncResult state - fallback
        """
        from apps.trading.services.status_sync import sync_task_status_from_celery

        sync_task_status_from_celery(self, self.get_celery_result())

    def cancel(self) -> bool:
        """Cancel the running task.

        Returns:
            bool: True if task was successfully cancelled, False otherwise
        """
        if self.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            result = self.get_celery_result()
            if result:
                result.revoke(terminate=True)
            self.status = TaskStatus.STOPPED
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at", "updated_at"])
            return True
        return False

    @property
    def duration(self) -> timedelta | None:
        """Calculate task execution duration.

        Returns:
            timedelta | None: Duration if both started_at and completed_at are set, None otherwise
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def set_result_data(self, data: Any) -> None:
        """Set result data, automatically using external storage if needed.

        Args:
            data: Result data to store
        """
        from apps.trading.services.storage import ExternalStorageService

        storage_service = ExternalStorageService()
        inline_data, external_ref = storage_service.store_if_needed(self.pk, data)

        self.result_data = inline_data
        self.result_data_external_ref = external_ref
        self.save(update_fields=["result_data", "result_data_external_ref", "updated_at"])

    def get_result_data(self) -> Any:
        """Get result data from inline or external storage.

        Returns:
            Any: The result data

        Raises:
            FileNotFoundError: If external reference is invalid
        """
        from apps.trading.services.storage import ExternalStorageService

        storage_service = ExternalStorageService()
        return storage_service.retrieve_data(self.result_data, self.result_data_external_ref)

    def clear_result_data(self) -> None:
        """Clear result data from both inline and external storage."""
        from apps.trading.services.storage import ExternalStorageService

        # Delete external data if it exists
        if self.result_data_external_ref:
            storage_service = ExternalStorageService()
            storage_service.delete_external_data(self.result_data_external_ref)

        # Clear both fields
        self.result_data = None
        self.result_data_external_ref = None
        self.save(update_fields=["result_data", "result_data_external_ref", "updated_at"])

    def start(self) -> None:
        """
        Start the trading task.

        Transitions task to running state. The actual Executions record
        will be created by the Celery task that performs the trading.
        Enforces one active task per account constraint.

        Raises:
            ValueError: If task is already running or another task is running on the account
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")

        # Check if another task is running on this account
        other_running_tasks = TradingTasks.objects.filter(
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

        # Fetch trading_mode from OANDA if not set
        if not self.trading_mode or self.trading_mode == TradingMode.NETTING:
            try:
                from apps.market.services.oanda import OandaService

                oanda_service = OandaService(self.oanda_account)
                position_mode = oanda_service.get_account_position_mode()
                self.trading_mode = (
                    TradingMode.HEDGING if position_mode == "hedging" else TradingMode.NETTING
                )
            except Exception:
                # Default to netting if fetch fails
                self.trading_mode = TradingMode.NETTING

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "trading_mode", "updated_at"])

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

    def restart(self, *, clear_state: bool = True) -> bool:
        """Restart task from the beginning, clearing all execution data.

        Args:
            clear_state: Whether to clear persisted strategy state (default: True)

        Returns:
            bool: True if task was successfully restarted, False otherwise

        Raises:
            ValueError: If task is currently running or another task is running on the account
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Cannot restart a task that is currently running. Stop it first.")

        # Check if another task is running on this account
        other_running_tasks = TradingTasks.objects.filter(
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

        if self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.STOPPED,
            TaskStatus.STOPPED,
        ]:
            # Clear result data (including external storage)
            self.clear_result_data()

            # Clear all events associated with this task
            from apps.trading.models import TradingEvent

            TradingEvent.objects.filter(task_type="trading", task_id=self.pk).delete()

            # Clear all other execution data
            self.celery_task_id = None
            self.status = TaskStatus.CREATED
            self.started_at = None
            self.completed_at = None
            self.error_message = None
            self.error_traceback = None
            self.retry_count += 1

            if clear_state:
                self.strategy_state = {}

            self.save()
            return True
        return False

    def resume(self) -> bool:
        """Resume a cancelled or interrupted task, preserving execution context.

        For trading tasks, this allows resuming from STOPPED state.
        STOPPED is the normal completion state for trading tasks, and they can be
        resumed to continue trading.

        Returns:
            bool: True if task was successfully resumed, False otherwise

        Raises:
            ValueError: If another task is running on the account
        """
        if self.status not in [TaskStatus.STOPPED, TaskStatus.STOPPED]:
            return False

        # Check if another task is running on this account
        other_running_tasks = TradingTasks.objects.filter(
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

        # Keep existing execution data but reset status
        self.celery_task_id = None
        self.status = TaskStatus.CREATED
        self.completed_at = None
        self.save()
        return True

    def copy(self, new_name: str) -> "TradingTasks":
        """
        Create a copy of this task with a new name.

        All task properties are duplicated except name and ID.

        Args:
            new_name: Name for the new task

        Returns:
            TradingTasks: The newly created task

        Raises:
            ValueError: If new_name is the same as current name or already exists
        """
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        # Check if name already exists for this user
        if TradingTasks.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A trading task with name '{new_name}' already exists")

        # Create copy
        new_task = TradingTasks.objects.create(
            user=self.user,
            config=self.config,
            oanda_account=self.oanda_account,
            name=new_name,
            description=self.description,
            status=TaskStatus.CREATED,
        )

        return new_task

    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        """Delete the task and stop any running Celery tasks."""
        from apps.trading.services.lock import TaskLockManager

        # Stop the Celery task if running
        if self.status == TaskStatus.RUNNING:
            lock_manager = TaskLockManager()
            lock_manager.set_cancellation_flag(TaskType.TRADING, self.pk)

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
    def pip_size(self) -> Decimal:
        """Get pip_size as Decimal with default value.

        Returns:
            Decimal: Pip size for the instrument, defaults to 0.01 if not set

        Example:
            >>> task = TradingTasks.objects.get(id=1)
            >>> pip_size = task.pip_size  # Always returns Decimal
        """
        if self._pip_size is not None:
            return Decimal(str(self._pip_size))
        return Decimal("0.01")

    @property
    def account_id(self) -> int:
        """Get the OANDA account ID.

        Returns:
            int: The primary key of the associated OANDA account
        """
        return self.oanda_account_id  # type: ignore[return-value]


class FloorSide(models.TextChoices):
    """Side used by the floor strategy for layering."""

    LONG = "long", "Long"
    SHORT = "short", "Short"
