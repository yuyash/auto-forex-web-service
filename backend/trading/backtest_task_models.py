"""
BacktestTask model for task-based strategy configuration.

This module contains the BacktestTask model which represents a persistent
backtesting task with reusable configuration.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.1, 4.2, 4.3, 4.4, 4.5
"""

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .enums import DataSource, TaskStatus, TaskType

User = get_user_model()


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

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.1, 4.2, 4.3, 4.4, 4.5
    """

    objects = BacktestTaskManager()

    user = models.ForeignKey(
        User,
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
    oanda_account = models.ForeignKey(
        "accounts.OandaAccount",
        on_delete=models.PROTECT,
        related_name="backtest_tasks",
        null=True,
        blank=True,
        help_text="OANDA account used for this backtest (practice accounts only)",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this backtest task",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this backtest task",
    )
    data_source = models.CharField(
        max_length=20,
        default=DataSource.ATHENA,
        choices=DataSource.choices,
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
        max_length=10,
        default="USD_JPY",
        help_text="Currency pair to backtest (e.g., 'USD_JPY', 'EUR_USD')",
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
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_backtest_task_name",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type})"

    def start(self) -> None:
        """
        Start the backtest task.

        Transitions task to running state. The actual TaskExecution record
        will be created by the Celery task that performs the backtest.

        Raises:
            ValueError: If task is already running
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def stop(self) -> None:
        """
        Stop a running backtest task.

        Transitions task to stopped state and marks current execution as stopped.

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

        # Send WebSocket notification
        from trading.services.notifications import send_task_status_notification

        send_task_status_notification(
            user_id=self.user.id,
            task_id=self.pk,
            task_name=self.name,
            task_type="backtest",
            status=TaskStatus.STOPPED,
            execution_id=latest_execution.id if latest_execution else None,
        )

    def rerun(self) -> None:
        """
        Rerun the backtest task from the beginning.

        Transitions task to running state. The actual TaskExecution record
        will be created by the Celery task that performs the backtest.
        Task can be in any state (completed, failed, stopped) to be rerun.

        Raises:
            ValueError: If task is currently running
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Cannot rerun a task that is currently running. Stop it first.")

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

    def copy(self, new_name: str) -> "BacktestTask":
        """
        Create a copy of this task with a new name.

        All task properties are duplicated except name and ID.

        Args:
            new_name: Name for the new task

        Returns:
            BacktestTask: The newly created task

        Raises:
            ValueError: If new_name is the same as current name or already exists
        """
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        # Check if name already exists for this user
        if BacktestTask.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A backtest task with name '{new_name}' already exists")

        # Create copy
        new_task = BacktestTask.objects.create(
            user=self.user,
            config=self.config,
            name=new_name,
            description=self.description,
            data_source=self.data_source,
            start_time=self.start_time,
            end_time=self.end_time,
            initial_balance=self.initial_balance,
            commission_per_trade=self.commission_per_trade,
            instrument=self.instrument,
            status=TaskStatus.CREATED,
        )

        return new_task

    def get_latest_execution(self) -> Any:
        """
        Get the most recent execution for this task.

        Returns:
            TaskExecution or None: The latest execution, or None if no executions exist
        """
        # Import here to avoid circular dependency
        from .execution_models import TaskExecution

        return (
            TaskExecution.objects.filter(
                task_type=TaskType.BACKTEST,
                task_id=self.pk,
            )
            .order_by("-execution_number")
            .first()
        )

    def get_execution_history(self) -> Any:
        """
        Get all executions for this task, ordered by execution number.

        Returns:
            QuerySet: All executions for this task
        """
        # Import here to avoid circular dependency
        from .execution_models import TaskExecution

        return TaskExecution.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=self.pk,
        ).order_by("-execution_number")

    def validate_configuration(self) -> tuple[bool, str | None]:
        """
        Validate task configuration before execution.

        Validates:
        - Date range (start_time < end_time)
        - Strategy configuration parameters
        - Initial balance is positive
        - OANDA account (if specified) is practice account

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate date range and initial balance
        if self.start_time >= self.end_time:
            return False, "start_time must be before end_time"
        if self.initial_balance <= 0:
            return False, "initial_balance must be positive"

        # Validate strategy configuration
        is_valid, error_message = self.config.validate_parameters()
        return (
            (True, None)
            if is_valid
            else (False, f"Configuration validation failed: {error_message}")
        )
