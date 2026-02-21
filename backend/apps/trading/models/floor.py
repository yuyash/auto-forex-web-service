"""Floor strategy models."""

from decimal import Decimal
from uuid import uuid4

from django.db import models

from apps.trading.enums import Direction


class Layer(models.Model):
    """
    Trading layer for Floor strategy.

    A layer represents a group of positions opened at different price levels
    as the market retraces. Each layer tracks its positions in FIFO order.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this layer",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this layer belongs to",
    )
    index = models.IntegerField(
        help_text="Layer index (0, 1, 2, ...)",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        help_text="Layer direction (LONG/SHORT)",
    )
    retracement_count = models.IntegerField(
        default=0,
        help_text="Number of retracements in this layer",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the layer is currently active",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this layer was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this layer was last updated",
    )

    class Meta:
        db_table = "floor_layers"
        verbose_name = "Floor Layer"
        verbose_name_plural = "Floor Layers"
        ordering = ["task_id", "index"]
        indexes = [
            models.Index(fields=["task_id", "is_active", "index"]),
            models.Index(fields=["task_id", "index"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task_id", "index"],
                name="unique_task_layer_index",
            ),
        ]

    def __str__(self) -> str:
        status = "ACTIVE" if self.is_active else "CLOSED"
        return f"Layer {self.index} ({status}) - {self.direction} - {self.retracement_count} retracements"

    @property
    def total_units(self) -> Decimal:
        """Get total units across all positions in this layer."""
        from apps.trading.models.positions import Position

        positions = Position.objects.filter(
            task_id=self.task_id,
            layer_index=self.index,
            is_open=True,
        )
        return sum((Decimal(str(p.units)) for p in positions), Decimal("0"))

    @property
    def average_entry_price(self) -> Decimal:
        """Calculate weighted average entry price across all positions."""
        from apps.trading.models.positions import Position

        positions = Position.objects.filter(
            task_id=self.task_id,
            layer_index=self.index,
            is_open=True,
        )

        if not positions.exists():
            return Decimal("0")

        total_cost = sum(
            (p.entry_price * Decimal(str(abs(p.units))) for p in positions),
            Decimal("0"),
        )
        total_units = self.total_units

        return total_cost / total_units if total_units > 0 else Decimal("0")

    @property
    def position_count(self) -> int:
        """Get number of open positions in this layer."""
        from apps.trading.models.positions import Position

        return Position.objects.filter(
            task_id=self.task_id,
            layer_index=self.index,
            is_open=True,
        ).count()

    def close(self) -> None:
        """Mark layer as inactive."""
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def increment_retracement(self) -> None:
        """Increment retracement count."""
        self.retracement_count += 1
        self.save(update_fields=["retracement_count", "updated_at"])
