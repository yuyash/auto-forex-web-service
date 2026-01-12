"""apps.trading.events

Typed event classes for strategy events.

This module provides type-safe event classes for each EventType, making
it clear what fields are required for each event and enabling better
IDE support and compile-time checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.trading.enums import EventType


@dataclass
class StrategyEvent:
    """Base class for all strategy events.

    This is the abstract base class that all specific event types inherit from.
    It provides common fields and methods shared by all events.

    Attributes:
        event_type: Type of event (EventType enum value)
        timestamp: ISO format timestamp string (optional)

    Requirements: 1.2, 3.2
    """

    event_type: str  # EventType enum value
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for database storage.

        Returns:
            Dictionary representation of the event
        """
        result = {"event_type": self.event_type}
        if self.timestamp:
            result["timestamp"] = self.timestamp
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "StrategyEvent":
        """Create StrategyEvent from dictionary.

        This factory method creates the appropriate subclass based on event_type.

        Args:
            event_dict: Dictionary containing event data

        Returns:
            Appropriate StrategyEvent subclass instance
        """
        event_type = event_dict.get("event_type") or event_dict.get("type", "")

        # Map event_type to appropriate class
        if event_type == EventType.INITIAL_ENTRY:
            return InitialEntryEvent.from_dict(event_dict)
        elif event_type == EventType.RETRACEMENT:
            return RetracementEvent.from_dict(event_dict)
        elif event_type == EventType.TAKE_PROFIT:
            return TakeProfitEvent.from_dict(event_dict)
        elif event_type == EventType.ADD_LAYER:
            return AddLayerEvent.from_dict(event_dict)
        elif event_type == EventType.REMOVE_LAYER:
            return RemoveLayerEvent.from_dict(event_dict)
        elif event_type == EventType.VOLATILITY_LOCK:
            return VolatilityLockEvent.from_dict(event_dict)
        elif event_type == EventType.MARGIN_PROTECTION:
            return MarginProtectionEvent.from_dict(event_dict)
        else:
            # Generic event for unknown types
            return GenericStrategyEvent.from_dict(event_dict)


@dataclass
class InitialEntryEvent(StrategyEvent):
    """Event for opening an initial position layer.

    Attributes:
        layer_number: Layer number being opened
        direction: Trade direction ("long" or "short")
        price: Entry price
        units: Position size
        retracement_count: Number of retracements (default: 0)

    Example:
        >>> event = InitialEntryEvent(
        ...     event_type=EventType.INITIAL_ENTRY,
        ...     layer_number=1,
        ...     direction="long",
        ...     price=Decimal("150.25"),
        ...     units=1000,
        ... )
    """

    layer_number: int = 0
    direction: str = ""
    price: Decimal = Decimal("0")
    units: int = 0
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.INITIAL_ENTRY

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": self.direction,
                "price": str(self.price),
                "units": self.units,
                "retracement_count": self.retracement_count,
            }
        )
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "InitialEntryEvent":
        from decimal import Decimal as D

        price_raw = event_dict.get("price", "0")
        price = D(str(price_raw)) if price_raw else D("0")

        return cls(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=event_dict.get("timestamp"),
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            price=price,
            units=int(event_dict.get("units", 0)),
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class RetracementEvent(StrategyEvent):
    """Event for opening a retracement position.

    Attributes:
        layer_number: Layer number being retracted
        direction: Trade direction ("long" or "short")
        price: Entry price
        units: Position size
        retracement_count: Number of retracements for this layer

    Example:
        >>> event = RetracementEvent(
        ...     event_type=EventType.RETRACEMENT,
        ...     layer_number=1,
        ...     direction="long",
        ...     price=Decimal("150.15"),
        ...     units=500,
        ...     retracement_count=2,
        ... )
    """

    layer_number: int = 0
    direction: str = ""
    price: Decimal = Decimal("0")
    units: int = 0
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.RETRACEMENT

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": self.direction,
                "price": str(self.price),
                "units": self.units,
                "retracement_count": self.retracement_count,
            }
        )
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "RetracementEvent":
        from decimal import Decimal as D

        price_raw = event_dict.get("price", "0")
        price = D(str(price_raw)) if price_raw else D("0")

        return cls(
            event_type=EventType.RETRACEMENT,
            timestamp=event_dict.get("timestamp"),
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            price=price,
            units=int(event_dict.get("units", 0)),
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class TakeProfitEvent(StrategyEvent):
    """Event for closing a position with profit.

    Attributes:
        layer_number: Layer number being closed
        direction: Trade direction ("long" or "short")
        entry_price: Original entry price
        exit_price: Exit price
        units: Position size
        pnl: Profit/loss in account currency
        pips: Profit/loss in pips
        entry_time: Entry timestamp (optional)
        retracement_count: Number of retracements (optional)

    Example:
        >>> event = TakeProfitEvent(
        ...     event_type=EventType.TAKE_PROFIT,
        ...     layer_number=1,
        ...     direction="long",
        ...     entry_price=Decimal("150.25"),
        ...     exit_price=Decimal("150.35"),
        ...     units=1000,
        ...     pnl=Decimal("100.00"),
        ...     pips=Decimal("10.0"),
        ... )
    """

    layer_number: int = 0
    direction: str = ""
    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = Decimal("0")
    units: int = 0
    pnl: Decimal = Decimal("0")
    pips: Decimal = Decimal("0")
    entry_time: str | None = None
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.TAKE_PROFIT

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": self.direction,
                "entry_price": str(self.entry_price),
                "exit_price": str(self.exit_price),
                "price": str(self.exit_price),  # Alias for backward compatibility
                "units": self.units,
                "pnl": str(self.pnl),
                "pips": str(self.pips),
                "retracement_count": self.retracement_count,
            }
        )
        if self.entry_time:
            result["entry_time"] = self.entry_time
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "TakeProfitEvent":
        from decimal import Decimal as D

        entry_price_raw = event_dict.get("entry_price", "0")
        entry_price = D(str(entry_price_raw)) if entry_price_raw else D("0")

        exit_price_raw = event_dict.get("exit_price") or event_dict.get("price", "0")
        exit_price = D(str(exit_price_raw)) if exit_price_raw else D("0")

        pnl_raw = event_dict.get("pnl", "0")
        pnl = D(str(pnl_raw)) if pnl_raw else D("0")

        pips_raw = event_dict.get("pips", "0")
        pips = D(str(pips_raw)) if pips_raw else D("0")

        return cls(
            event_type=EventType.TAKE_PROFIT,
            timestamp=event_dict.get("timestamp"),
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            entry_price=entry_price,
            exit_price=exit_price,
            units=int(event_dict.get("units", 0)),
            pnl=pnl,
            pips=pips,
            entry_time=event_dict.get("entry_time"),
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class AddLayerEvent(StrategyEvent):
    """Event for adding a new layer to the strategy.

    Attributes:
        layer_number: Layer number being added

    Example:
        >>> event = AddLayerEvent(
        ...     event_type=EventType.ADD_LAYER,
        ...     layer_number=2,
        ... )
    """

    layer_number: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.ADD_LAYER

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["layer_number"] = self.layer_number
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "AddLayerEvent":
        return cls(
            event_type=EventType.ADD_LAYER,
            timestamp=event_dict.get("timestamp"),
            layer_number=int(event_dict.get("layer_number", 0)),
        )


@dataclass
class RemoveLayerEvent(StrategyEvent):
    """Event for removing a layer from the strategy.

    Attributes:
        layer_number: Layer number being removed

    Example:
        >>> event = RemoveLayerEvent(
        ...     event_type=EventType.REMOVE_LAYER,
        ...     layer_number=3,
        ... )
    """

    layer_number: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.REMOVE_LAYER

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["layer_number"] = self.layer_number
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "RemoveLayerEvent":
        return cls(
            event_type=EventType.REMOVE_LAYER,
            timestamp=event_dict.get("timestamp"),
            layer_number=int(event_dict.get("layer_number", 0)),
        )


@dataclass
class VolatilityLockEvent(StrategyEvent):
    """Event for strategy locked due to high volatility.

    Attributes:
        reason: Reason for the lock
        atr_value: ATR value that triggered the lock (optional)
        threshold: ATR threshold (optional)

    Example:
        >>> event = VolatilityLockEvent(
        ...     event_type=EventType.VOLATILITY_LOCK,
        ...     reason="ATR exceeded threshold",
        ...     atr_value=Decimal("0.25"),
        ...     threshold=Decimal("0.20"),
        ... )
    """

    reason: str = ""
    atr_value: Decimal | None = None
    threshold: Decimal | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.VOLATILITY_LOCK

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["reason"] = self.reason
        if self.atr_value is not None:
            result["atr_value"] = str(self.atr_value)
        if self.threshold is not None:
            result["threshold"] = str(self.threshold)
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "VolatilityLockEvent":
        from decimal import Decimal as D

        atr_value_raw = event_dict.get("atr_value")
        atr_value = D(str(atr_value_raw)) if atr_value_raw else None

        threshold_raw = event_dict.get("threshold")
        threshold = D(str(threshold_raw)) if threshold_raw else None

        return cls(
            event_type=EventType.VOLATILITY_LOCK,
            timestamp=event_dict.get("timestamp"),
            reason=str(event_dict.get("reason", "")),
            atr_value=atr_value,
            threshold=threshold,
        )


@dataclass
class MarginProtectionEvent(StrategyEvent):
    """Event for margin protection triggered.

    Attributes:
        reason: Reason for margin protection
        current_margin: Current margin level (optional)
        threshold: Margin threshold (optional)
        positions_closed: Number of positions closed (optional)

    Example:
        >>> event = MarginProtectionEvent(
        ...     event_type=EventType.MARGIN_PROTECTION,
        ...     reason="Margin threshold exceeded",
        ...     current_margin=Decimal("0.05"),
        ...     threshold=Decimal("0.10"),
        ...     positions_closed=2,
        ... )
    """

    reason: str = ""
    current_margin: Decimal | None = None
    threshold: Decimal | None = None
    positions_closed: int | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.MARGIN_PROTECTION

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["reason"] = self.reason
        if self.current_margin is not None:
            result["current_margin"] = str(self.current_margin)
        if self.threshold is not None:
            result["threshold"] = str(self.threshold)
        if self.positions_closed is not None:
            result["positions_closed"] = self.positions_closed
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "MarginProtectionEvent":
        from decimal import Decimal as D

        current_margin_raw = event_dict.get("current_margin")
        current_margin = D(str(current_margin_raw)) if current_margin_raw else None

        threshold_raw = event_dict.get("threshold")
        threshold = D(str(threshold_raw)) if threshold_raw else None

        return cls(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=event_dict.get("timestamp"),
            reason=str(event_dict.get("reason", "")),
            current_margin=current_margin,
            threshold=threshold,
            positions_closed=event_dict.get("positions_closed"),
        )


@dataclass
class GenericStrategyEvent(StrategyEvent):
    """Generic event for custom or unknown event types.

    This class is used for event types that don't have a specific class,
    allowing flexibility for custom strategies while maintaining type safety.

    Attributes:
        data: Event-specific data dictionary

    Example:
        >>> event = GenericStrategyEvent(
        ...     event_type="custom_signal",
        ...     data={"signal": "buy", "confidence": 0.85},
        ... )
    """

    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(self.data)
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "GenericStrategyEvent":
        event_type = event_dict.get("event_type") or event_dict.get("type", "")
        timestamp = event_dict.get("timestamp")

        # Extract data (everything except event_type and timestamp)
        data = {k: v for k, v in event_dict.items() if k not in {"event_type", "type", "timestamp"}}

        return cls(
            event_type=str(event_type),
            timestamp=str(timestamp) if timestamp else None,
            data=data,
        )
