"""Tick data dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class Tick:
    """Market tick data point.

    This dataclass represents a single market data point containing
    price information for a trading instrument at a specific time.

    All prices are stored as Decimal for precise calculations.
    All fields are required (no None values).

    Attributes:
        instrument: Trading instrument (e.g., "USD_JPY")
        timestamp: Tick timestamp as datetime (timezone-aware)
        bid: Bid price as Decimal
        ask: Ask price as Decimal
        mid: Mid price as Decimal (calculated from bid/ask if not provided)

    Requirements: 9.2, 18.4

    Example:
        >>> from datetime import datetime, UTC
        >>> tick = Tick(
        ...     instrument="USD_JPY",
        ...     timestamp=datetime.now(UTC),
        ...     bid=Decimal("150.25"),
        ...     ask=Decimal("150.27"),
        ...     mid=Decimal("150.26"),
        ... )
    """

    instrument: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    mid: Decimal

    def __post_init__(self) -> None:
        """Calculate mid if not provided."""
        if self.mid == Decimal("0") or self.mid is None:
            calculated_mid = (self.bid + self.ask) / Decimal("2")
            object.__setattr__(self, "mid", calculated_mid)

    @staticmethod
    def create(
        instrument: str,
        timestamp: datetime,
        bid: Decimal,
        ask: Decimal,
        mid: Decimal | None = None,
    ) -> "Tick":
        """Create a Tick with automatic mid calculation if not provided.

        Args:
            instrument: Trading instrument
            timestamp: Tick timestamp
            bid: Bid price
            ask: Ask price
            mid: Mid price (calculated from bid/ask if None)

        Returns:
            Tick instance
        """
        if mid is None:
            mid = (bid + ask) / Decimal("2")
        return Tick(
            instrument=instrument,
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            mid=mid,
        )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Tick":
        """Create Tick from dictionary.

        Args:
            data: Dictionary containing tick data

        Returns:
            Tick: Tick instance with Decimal prices and datetime timestamp

        Raises:
            ValueError: If required fields are missing or invalid
        """
        from datetime import UTC, datetime

        instrument = data.get("instrument")
        if not instrument:
            raise ValueError("Tick must have instrument")

        timestamp_raw = data.get("timestamp")
        if not timestamp_raw:
            raise ValueError("Tick must have timestamp")

        # Parse timestamp
        try:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                timestamp_str = str(timestamp_raw).strip()
                if timestamp_str.endswith("Z"):
                    timestamp_str = timestamp_str[:-1] + "+00:00"
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid timestamp: {exc}") from exc

        bid_raw = data.get("bid")
        ask_raw = data.get("ask")
        mid_raw = data.get("mid")

        if bid_raw is None or ask_raw is None or mid_raw is None:
            raise ValueError("Tick must have bid, ask, and mid prices")

        try:
            bid = Decimal(str(bid_raw))
            ask = Decimal(str(ask_raw))
            mid = Decimal(str(mid_raw))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"Invalid price values in tick: {exc}") from exc

        return Tick(
            instrument=str(instrument),
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            mid=mid,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format.

        Returns:
            dict: Dictionary representation with Decimal values as strings
                  and timestamp as ISO format string
        """
        return {
            "instrument": self.instrument,
            "timestamp": self.timestamp.isoformat(),
            "bid": str(self.bid),
            "ask": str(self.ask),
            "mid": str(self.mid),
        }
