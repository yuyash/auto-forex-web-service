"""Execution state snapshot models."""

from django.db import models

class ExecutionStateSnapshot(models.Model):
    """Periodic state snapshots for task execution resumability.

    This model stores snapshots of execution state at regular intervals,
    enabling tasks to resume from where they left off after stopping or
    failing. Each snapshot includes the complete strategy state, account
    balance, open positions, and progress tracking.

    Requirements: 4.1, 4.2
    """

    execution = models.ForeignKey(
        "trading.TaskExecution",
        on_delete=models.CASCADE,
        related_name="state_snapshots",
        help_text="Associated task execution",
    )
    sequence = models.IntegerField(
        help_text="Monotonic sequence number for this execution",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the snapshot was created",
    )
    strategy_state = models.JSONField(
        default=dict,
        help_text="Strategy-specific state dictionary",
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Current account balance",
    )
    open_positions = models.JSONField(
        default=list,
        help_text="List of open position dictionaries",
    )
    ticks_processed = models.IntegerField(
        default=0,
        help_text="Number of ticks processed so far",
    )
    last_tick_timestamp = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="ISO format timestamp of last processed tick",
    )
    metrics = models.JSONField(
        default=dict,
        help_text="Current performance metrics dictionary",
    )

    class Meta:
        db_table = "execution_state_snapshots"
        verbose_name = "Execution State Snapshot"
        verbose_name_plural = "Execution State Snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "sequence"],
                name="unique_execution_state_snapshot",
            )
        ]
        indexes = [
            models.Index(fields=["execution", "sequence"]),
            models.Index(fields=["execution", "timestamp"]),
        ]
        ordering = ["-sequence"]

    def __str__(self) -> str:
        return f"StateSnapshot(exec={self.execution_id}, seq={self.sequence})"  # type: ignore[attr-defined]

