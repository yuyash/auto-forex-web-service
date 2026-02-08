"""Tick data model for market analysis."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class TickData(models.Model):
    """
    Historical tick data for market analysis and backtesting.

    Stores bid, ask, and mid prices for each instrument at specific timestamps.
    Includes data retention policy for automatic cleanup of old data.
    """

    instrument = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Timestamp when the tick was received",
    )

    # Django 5.2+ supports composite primary keys.
    # Keep the canonical identity for ticks as (instrument, timestamp).
    pk = models.CompositePrimaryKey("instrument", "timestamp")
    bid = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Bid price",
    )
    ask = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Ask price",
    )
    mid = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Mid price (average of bid and ask)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the record was created",
    )

    class Meta:
        db_table = "tick_data"
        verbose_name = "Tick Data"
        verbose_name_plural = "Tick Data"
        indexes = [
            # Single field indexes for basic queries
            models.Index(fields=["instrument"]),
            models.Index(fields=["timestamp"]),
            # Index for data retention cleanup
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.instrument} @ {self.timestamp} - Bid: {self.bid}, Ask: {self.ask}"

    def save(self, *args, **kwargs) -> None:
        """
        Override save to automatically calculate mid if not provided.
        """
        # Calculate mid price if not provided
        current_mid = getattr(self, "mid", None)
        if current_mid is None or current_mid == 0:
            self.mid = self.calculate_mid(self.bid, self.ask)

        super().save(*args, **kwargs)

    @property
    def spread(self) -> Decimal:
        # Keep this simple for runtime correctness and static analysis.
        return Decimal(self.ask) - Decimal(self.bid)

    @classmethod
    def get_retention_days(cls) -> int:
        """
        Get the data retention period in days from settings.

        Returns:
            Number of days to retain tick data (default: 90)
        """
        return getattr(settings, "TICK_DATA_RETENTION_DAYS", 90)

    @classmethod
    def cleanup_old_data(cls, retention_days: int | None = None) -> int:
        """
        Delete tick data older than the retention period.

        Args:
            retention_days: Number of days to retain (uses default if None)

        Returns:
            Number of records deleted
        """
        if retention_days is None:
            retention_days = cls.get_retention_days()

        cutoff_date = timezone.now() - timedelta(days=retention_days)
        deleted_count, _ = cls.objects.filter(created_at__lt=cutoff_date).delete()
        return deleted_count

    @staticmethod
    def calculate_mid(bid: Decimal, ask: Decimal) -> Decimal:
        """
        Calculate mid price from bid and ask.

        Args:
            bid: Bid price
            ask: Ask price

        Returns:
            Mid price (average of bid and ask)
        """
        return (bid + ask) / Decimal("2")

    @staticmethod
    def calculate_spread(bid: Decimal, ask: Decimal) -> Decimal:
        """
        Calculate spread from bid and ask.

        Args:
            bid: Bid price
            ask: Ask price

        Returns:
            Spread (difference between ask and bid)
        """
        return ask - bid
