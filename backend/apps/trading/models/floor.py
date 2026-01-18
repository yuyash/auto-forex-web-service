"""Floor strategy state models."""

from decimal import Decimal

from django.db import models

from apps.trading.enums import TaskStatus


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
        "trading.TradingTasks",
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
