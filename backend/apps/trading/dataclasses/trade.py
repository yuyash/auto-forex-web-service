"""Trade-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class TradeData:
    """Data for a trade execution event.

    This dataclass represents the information about a trade that was
    executed, including entry/exit details, profit/loss, and metadata.
    """

    direction: str
    units: int
    entry_price: Decimal
    exit_price: Decimal | None = None
    pnl: Decimal | None = None
    pips: Decimal | None = None
    order_id: str | None = None
    position_id: str | None = None
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format.

        Returns:
            dict: Dictionary representation with Decimal values converted to strings
        """
        return {
            "direction": self.direction,
            "units": self.units,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price) if self.exit_price is not None else None,
            "pnl": str(self.pnl) if self.pnl is not None else None,
            "pips": str(self.pips) if self.pips is not None else None,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class OpenPosition:
    """Open position data for execution tracking.

    Represents an open trading position with entry details and current state.
    This is used for tracking positions during strategy execution, distinct
    from OANDA API's Position model which includes account-specific details.

    Attributes:
        position_id: Unique position identifier
        instrument: Trading instrument (e.g., "USD_JPY")
        direction: Position direction ("long" or "short")
        units: Number of units in the position
        entry_price: Entry price for the position
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss in account currency
        unrealized_pips: Unrealized profit/loss in pips
        timestamp: Position open timestamp (ISO format)

    Requirements: 1.3, 15.1

    Example:
        >>> position = OpenPosition(
        ...     position_id="12345",
        ...     instrument="USD_JPY",
        ...     direction="long",
        ...     units=1000,
        ...     entry_price=Decimal("150.25"),
        ...     current_price=Decimal("150.35"),
        ...     unrealized_pnl=Decimal("100.00"),
        ...     unrealized_pips=Decimal("10.0"),
        ...     timestamp="2024-01-01T00:00:00Z",
        ... )
    """

    position_id: str
    instrument: str
    direction: str
    units: int
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    unrealized_pips: Decimal
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format.

        Returns:
            dict: Dictionary representation with Decimal values converted to strings
        """
        return {
            "position_id": self.position_id,
            "instrument": self.instrument,
            "direction": self.direction,
            "units": self.units,
            "entry_price": str(self.entry_price),
            "current_price": str(self.current_price),
            "unrealized_pnl": str(self.unrealized_pnl),
            "unrealized_pips": str(self.unrealized_pips),
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "OpenPosition":
        """Create OpenPosition from dictionary.

        Args:
            data: Dictionary containing position data

        Returns:
            OpenPosition: OpenPosition instance
        """
        return OpenPosition(
            position_id=str(data.get("position_id", "")),
            instrument=str(data.get("instrument", "")),
            direction=str(data.get("direction", "")),
            units=int(data.get("units", 0)),
            entry_price=Decimal(str(data.get("entry_price", "0"))),
            current_price=Decimal(str(data.get("current_price", "0"))),
            unrealized_pnl=Decimal(str(data.get("unrealized_pnl", "0"))),
            unrealized_pips=Decimal(str(data.get("unrealized_pips", "0"))),
            timestamp=str(data.get("timestamp", "")),
        )
