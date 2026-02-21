"""Execution state persistence model."""

from __future__ import annotations

from django.db import models

from apps.trading.models.base import UUIDModel


class ExecutionState(UUIDModel):
    """Persistent storage for execution state.

    This model stores the complete execution state for a task, including
    strategy-specific state, current balance, and progress tracking.
    It replaces the result_data JSON field and FloorStrategyTaskState model.

    The model uses a polymorphic reference to tasks (BacktestTask or TradingTask)
    via task_type and task_id fields, allowing it to work with both task types.

    Attributes:
        task_type: Type of task ("backtest" or "trading")
        task_id: UUID of the task
        celery_task_id: Celery task ID for tracking
        strategy_state: Strategy-specific state as JSON
        current_balance: Current account balance
        ticks_processed: Number of ticks processed
        last_tick_timestamp: Timestamp of last processed tick
        created_at: When this state was first created (from UUIDModel)
        updated_at: When this state was last updated (from UUIDModel)
    """

    task_type = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Type of task: 'backtest' or 'trading'",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the associated task",
    )
    celery_task_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Celery task ID for tracking execution",
    )

    # Execution state fields
    strategy_state = models.JSONField(
        default=dict,
        blank=True,
        help_text="Strategy-specific state as JSON",
    )
    current_balance = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="Current account balance",
    )
    ticks_processed = models.IntegerField(
        default=0,
        help_text="Number of ticks processed so far",
    )
    last_tick_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last processed tick",
    )
    last_tick_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Mid price of the last processed tick",
    )

    class Meta:
        db_table = "execution_state"
        verbose_name = "Execution State"
        verbose_name_plural = "Execution States"
        indexes = [
            models.Index(fields=["task_type", "task_id", "celery_task_id"]),
            models.Index(fields=["task_type", "task_id"]),
            models.Index(fields=["celery_task_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "celery_task_id"],
                name="unique_task_celery_execution_state",
            )
        ]

    def __str__(self) -> str:
        return f"ExecutionState({self.task_type}:{self.task_id}, ticks={self.ticks_processed})"
