"""
TradingTask model for task-based strategy configuration.

This module contains the TradingTask model which represents a persistent
live trading task with reusable configuration.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from accounts.models import OandaAccount

from .enums import TaskStatus, TaskType

User = get_user_model()


class TradingTask(models.Model):
    """
    Persistent live trading task with reusable configuration.

    A TradingTask represents a live trading operation with specific configuration
    and account. Tasks can be started, stopped, paused, and resumed multiple times,
    with each execution tracked separately.

    Only one task can be running per account at a time.

    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="trading_tasks",
        help_text="User who created this trading task",
    )
    config = models.ForeignKey(
        "StrategyConfig",
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

    def start(self) -> Any:
        """
        Start the trading task.

        Creates a new TaskExecution record and transitions task to running state.
        Enforces one active task per account constraint.

        Returns:
            TaskExecution: The created execution record

        Raises:
            ValueError: If task is already running or another task is running on the account
        """
        if self.status == TaskStatus.RUNNING:
            raise ValueError("Task is already running")

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=self.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(id=self.id)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        # Import here to avoid circular dependency
        from .execution_models import TaskExecution

        # Calculate next execution number
        last_execution = (
            TaskExecution.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.id,
            )
            .order_by("-execution_number")
            .first()
        )
        next_execution_number = (last_execution.execution_number + 1) if last_execution else 1

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

        # Create new execution
        execution = TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=self.id,
            execution_number=next_execution_number,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        return execution

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
        ).exclude(id=self.id)

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

    def rerun(self) -> Any:
        """
        Rerun the trading task from the beginning.

        Creates a new execution with the same configuration. Task can be in any
        state (stopped, failed) to be rerun, but not running or paused.

        Returns:
            TaskExecution: The created execution record

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
        ).exclude(id=self.id)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                raise ValueError(
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )

        # Import here to avoid circular dependency
        from .execution_models import TaskExecution

        # Calculate next execution number
        last_execution = (
            TaskExecution.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.id,
            )
            .order_by("-execution_number")
            .first()
        )
        next_execution_number = (last_execution.execution_number + 1) if last_execution else 1

        # Update task status
        self.status = TaskStatus.RUNNING
        self.save(update_fields=["status", "updated_at"])

        # Create new execution
        execution = TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=self.id,
            execution_number=next_execution_number,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        return execution

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
        """
        Get the most recent execution for this task.

        Returns:
            TaskExecution or None: The latest execution, or None if no executions exist
        """
        # Import here to avoid circular dependency
        from .execution_models import TaskExecution

        return (
            TaskExecution.objects.filter(
                task_type=TaskType.TRADING,
                task_id=self.id,
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
            task_type=TaskType.TRADING,
            task_id=self.id,
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
        if self.oanda_account.user_id != self.user_id:
            return False, "Account does not belong to the user"

        # Validate account is active
        if not self.oanda_account.is_active:
            return False, "Account is not active"

        # Validate strategy configuration
        is_valid, error_message = self.config.validate_parameters()
        if not is_valid:
            return False, f"Configuration validation failed: {error_message}"

        return True, None
