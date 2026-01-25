"""Backtest task model."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from celery.result import AsyncResult
from django.db import models
from django.utils import timezone

from apps.trading.enums import DataSource, TaskStatus, TaskType, TradingMode
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
            # Clear all events associated with this task
            from apps.trading.models import TradingEvents

            TradingEvents.objects.filter(task_type="backtest", task_id=self.pk).delete()

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
