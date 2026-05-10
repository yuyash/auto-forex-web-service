"""Position models for trade execution."""

import logging
from decimal import Decimal
from uuid import uuid4

from django.db import models

from apps.trading.enums import Direction, TaskType

logger = logging.getLogger(__name__)


class Position(models.Model):
    """
    Active or historical position from task execution.

    Stores position details including entry/exit prices and timestamps.
    Positions are created when trades are opened and updated when closed.

    In Netting Mode: One position per instrument per task (aggregated).
    In Hedging Mode: Multiple independent positions per instrument per task.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
        help_text="Unique identifier for this position",
    )
    task_type = models.CharField(
        max_length=32,
        choices=TaskType.choices,
        db_index=True,
        help_text="Type of task (backtest or trading)",
    )
    task_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the task this position belongs to",
    )
    execution_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Execution run UUID (shared with Celery task_id)",
    )
    instrument = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Trading instrument (e.g., EUR_USD)",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        help_text="Position direction (LONG/SHORT)",
    )
    units = models.IntegerField(
        help_text="Number of units in position (positive for long, negative for short)",
    )
    entry_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="Average entry price",
    )
    entry_time = models.DateTimeField(
        db_index=True,
        help_text="When the position was opened",
    )
    exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Exit price (null if position is still open)",
    )
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the position was closed (null if still open)",
    )
    is_open = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the position is currently open",
    )
    layer_index = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Strategy-specific layer index for layered strategies "
            "(1-based: L1, L2, ...; null for strategies that do not use layers)"
        ),
    )
    retracement_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Retracement index for this position (0-based: R0=initial entry, R1=first retracement, ...)",
    )
    unrealized_pnl = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=Decimal("0"),
        help_text="Unrealized PnL based on the latest tick price. Updated each tick batch.",
    )
    planned_exit_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Planned exit price calculated at order time (e.g. take-profit target)",
    )
    planned_exit_price_formula = models.TextField(
        null=True,
        blank=True,
        help_text="Human-readable formula used to calculate planned_exit_price (e.g. '1.12345 + 0.00500')",
    )
    adverse_pips = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Pips distance from the previous entry when this position was opened",
    )
    stop_loss_price = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Stop-loss price calculated at entry time. Position is closed if market reaches this price.",
    )
    is_rebuild = models.BooleanField(
        default=False,
        help_text="Whether this position was rebuilt after a stop-loss close.",
    )
    oanda_trade_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="OANDA trade ID for trade-based close operations",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated",
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this position was created or updated by resumed event replay.",
    )

    class Meta:
        db_table = "positions"
        verbose_name = "Position"
        verbose_name_plural = "Positions"
        ordering = ["-entry_time"]
        indexes = [
            models.Index(fields=["task_type", "task_id", "-entry_time"]),
            models.Index(fields=["task_type", "task_id", "execution_id", "-entry_time"]),
            models.Index(
                fields=["task_type", "task_id", "execution_id", "updated_at"],
                name="pos_task_exec_upd_idx",
            ),
            models.Index(
                fields=[
                    "task_type",
                    "task_id",
                    "execution_id",
                    "is_open",
                    "direction",
                    "-entry_time",
                ],
                name="pos_task_exec_state_idx",
            ),
            models.Index(fields=["task_type", "task_id", "instrument", "is_open"]),
            models.Index(fields=["is_open", "-entry_time"]),
            models.Index(fields=["instrument", "is_open"]),
        ]

    def __str__(self) -> str:
        status = "OPEN" if self.is_open else "CLOSED"
        return f"{status} {self.direction} {self.units} {self.instrument} @ {self.entry_price}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        if "planned_exit_price" in field_names:
            index = field_names.index("planned_exit_price")
            instance._loaded_planned_exit_price = values[index]
        return instance

    def save(self, *args, **kwargs) -> None:
        """Override save to enforce planned_exit_price immutability.

        Once planned_exit_price is set and persisted, it cannot be changed.
        Comparison is rounded to the field's decimal_places (10) to avoid
        false positives from Decimal precision differences.
        """
        self._preserve_planned_exit_price(kwargs.get("update_fields"))
        super().save(*args, **kwargs)
        self._loaded_planned_exit_price = self.planned_exit_price

    def _preserve_planned_exit_price(self, update_fields) -> None:
        if not self.pk:
            return
        if update_fields is not None and "planned_exit_price" not in update_fields:
            return

        existing = getattr(self, "_loaded_planned_exit_price", None)
        if existing is None and hasattr(self, "_loaded_planned_exit_price"):
            return
        if existing is None:
            existing = (
                Position.objects.filter(pk=self.pk)
                .values_list("planned_exit_price", flat=True)
                .first()
            )
        if existing is None or self.planned_exit_price is None:
            return

        rounded_existing = round(Decimal(str(existing)), 10)
        rounded_new = round(Decimal(str(self.planned_exit_price)), 10)
        if rounded_new == rounded_existing:
            return

        logger.warning(
            "Attempted to change immutable planned_exit_price on position %s "
            "(from %s to %s) - preserving original",
            self.pk,
            existing,
            self.planned_exit_price,
        )
        self.planned_exit_price = existing

    def close(self, exit_price: Decimal, exit_time: models.DateTimeField) -> None:
        """
        Close the position.

        Args:
            exit_price: Price at which position was closed
            exit_time: Timestamp when position was closed
        """
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.is_open = False
