"""Persisted OHLC candles derived from historical tick data."""

from decimal import Decimal
from uuid import uuid4

from django.db import models


class MarketCandle(models.Model):
    """OHLC candle for local charting and backtest replay visualization."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    instrument = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    granularity = models.CharField(
        max_length=8,
        db_index=True,
        help_text="Candle granularity such as M1, M5, H1, H4, or D.",
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="UTC candle open timestamp.",
    )
    open = models.DecimalField(max_digits=20, decimal_places=10)
    high = models.DecimalField(max_digits=20, decimal_places=10)
    low = models.DecimalField(max_digits=20, decimal_places=10)
    close = models.DecimalField(max_digits=20, decimal_places=10)
    volume = models.PositiveIntegerField(
        default=0,
        help_text="Number of source ticks or lower-granularity candles in this candle.",
    )
    source = models.CharField(
        max_length=32,
        default="tick_data",
        help_text="Source used to build this candle.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_candles"
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["instrument", "granularity", "timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "granularity", "timestamp"],
                name="uniq_market_candle",
            )
        ]

    def __str__(self) -> str:
        return f"{self.instrument} {self.granularity} @ {self.timestamp}"

    @property
    def midpoint(self) -> Decimal:
        """Return the candle midpoint between high and low."""

        return (self.high + self.low) / Decimal("2")
