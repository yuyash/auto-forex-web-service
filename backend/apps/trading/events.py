"""apps.trading.events

Typed event classes for strategy events.

This module provides type-safe event classes for each EventType, making
it clear what fields are required for each event and enabling better
IDE support and compile-time checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
        timestamp: Event timestamp (optional)

    Requirements: 1.2, 3.2
    """

    event_type: EventType
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for database storage.

        Returns:
            Dictionary representation of the event
        """
        result = {"event_type": str(self.event_type.value)}
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()
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
        event_type_str = event_dict.get("event_type", "")
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            # Generic event for unknown types
            return GenericStrategyEvent.from_dict(event_dict)

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
        direction: Trade direction (Direction enum)
        price: Entry price
        units: Position size
        entry_time: Entry timestamp
        retracement_count: Number of retracements (default: 0)

    Example:
        >>> from apps.trading.strategies.floor.enums import Direction
        >>> event = InitialEntryEvent(
        ...     event_type=EventType.INITIAL_ENTRY,
        ...     layer_number=1,
        ...     direction=Direction.LONG,
        ...     price=Decimal("150.25"),
        ...     units=1000,
        ...     entry_time=datetime.now(),
        ... )
    """

    layer_number: int = 0
    direction: str = ""  # Will be Direction enum value
    price: Decimal = Decimal("0")
    units: int = 0
    entry_time: datetime | None = None
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.INITIAL_ENTRY

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": str(self.direction),
                "price": str(self.price),
                "units": self.units,
                "retracement_count": self.retracement_count,
            }
        )
        if self.entry_time:
            result["entry_time"] = self.entry_time.isoformat()
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "InitialEntryEvent":
        from decimal import Decimal as D

        price_raw = event_dict.get("price", "0")
        price = D(str(price_raw)) if price_raw else D("0")

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        entry_time_raw = event_dict.get("entry_time")
        entry_time = None
        if entry_time_raw:
            if isinstance(entry_time_raw, datetime):
                entry_time = entry_time_raw
            else:
                try:
                    entry_time = datetime.fromisoformat(str(entry_time_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=timestamp,
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            price=price,
            units=int(event_dict.get("units", 0)),
            entry_time=entry_time,
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class RetracementEvent(StrategyEvent):
    """Event for opening a retracement position.

    Attributes:
        layer_number: Layer number being retracted
        direction: Trade direction (Direction enum)
        price: Entry price
        units: Position size
        entry_time: Entry timestamp
        retracement_count: Number of retracements for this layer

    Example:
        >>> from apps.trading.strategies.floor.enums import Direction
        >>> event = RetracementEvent(
        ...     event_type=EventType.RETRACEMENT,
        ...     layer_number=1,
        ...     direction=Direction.LONG,
        ...     price=Decimal("150.15"),
        ...     units=500,
        ...     entry_time=datetime.now(),
        ...     retracement_count=2,
        ... )
    """

    layer_number: int = 0
    direction: str = ""  # Will be Direction enum value
    price: Decimal = Decimal("0")
    units: int = 0
    entry_time: datetime | None = None
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.RETRACEMENT

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": str(self.direction),
                "price": str(self.price),
                "units": self.units,
                "retracement_count": self.retracement_count,
            }
        )
        if self.entry_time:
            result["entry_time"] = self.entry_time.isoformat()
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "RetracementEvent":
        from decimal import Decimal as D

        price_raw = event_dict.get("price", "0")
        price = D(str(price_raw)) if price_raw else D("0")

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        entry_time_raw = event_dict.get("entry_time")
        entry_time = None
        if entry_time_raw:
            if isinstance(entry_time_raw, datetime):
                entry_time = entry_time_raw
            else:
                try:
                    entry_time = datetime.fromisoformat(str(entry_time_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.RETRACEMENT,
            timestamp=timestamp,
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            price=price,
            units=int(event_dict.get("units", 0)),
            entry_time=entry_time,
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class TakeProfitEvent(StrategyEvent):
    """Event for closing a position with profit.

    Attributes:
        layer_number: Layer number being closed
        direction: Trade direction (Direction enum)
        entry_price: Original entry price
        exit_price: Exit price
        units: Position size
        pnl: Profit/loss in account currency
        pips: Profit/loss in pips
        entry_time: Entry timestamp (optional)
        exit_time: Exit timestamp (optional)
        retracement_count: Number of retracements (optional)

    Example:
        >>> from apps.trading.strategies.floor.enums import Direction
        >>> event = TakeProfitEvent(
        ...     event_type=EventType.TAKE_PROFIT,
        ...     layer_number=1,
        ...     direction=Direction.LONG,
        ...     entry_price=Decimal("150.25"),
        ...     exit_price=Decimal("150.35"),
        ...     units=1000,
        ...     pnl=Decimal("100.00"),
        ...     pips=Decimal("10.0"),
        ...     entry_time=datetime.now(),
        ...     exit_time=datetime.now(),
        ... )
    """

    layer_number: int = 0
    direction: str = ""  # Will be Direction enum value
    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = Decimal("0")
    units: int = 0
    pnl: Decimal = Decimal("0")
    pips: Decimal = Decimal("0")
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    retracement_count: int = 0

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.TAKE_PROFIT

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "layer_number": self.layer_number,
                "direction": str(self.direction),
                "entry_price": str(self.entry_price),
                "exit_price": str(self.exit_price),
                "units": self.units,
                "pnl": str(self.pnl),
                "pips": str(self.pips),
                "retracement_count": self.retracement_count,
            }
        )
        if self.entry_time:
            result["entry_time"] = self.entry_time.isoformat()
        if self.exit_time:
            result["exit_time"] = self.exit_time.isoformat()
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "TakeProfitEvent":
        from decimal import Decimal as D

        entry_price_raw = event_dict.get("entry_price", "0")
        entry_price = D(str(entry_price_raw)) if entry_price_raw else D("0")

        exit_price_raw = event_dict.get("exit_price", "0")
        exit_price = D(str(exit_price_raw)) if exit_price_raw else D("0")

        pnl_raw = event_dict.get("pnl", "0")
        pnl = D(str(pnl_raw)) if pnl_raw else D("0")

        pips_raw = event_dict.get("pips", "0")
        pips = D(str(pips_raw)) if pips_raw else D("0")

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        entry_time_raw = event_dict.get("entry_time")
        entry_time = None
        if entry_time_raw:
            if isinstance(entry_time_raw, datetime):
                entry_time = entry_time_raw
            else:
                try:
                    entry_time = datetime.fromisoformat(str(entry_time_raw))
                except (ValueError, TypeError):
                    pass

        exit_time_raw = event_dict.get("exit_time")
        exit_time = None
        if exit_time_raw:
            if isinstance(exit_time_raw, datetime):
                exit_time = exit_time_raw
            else:
                try:
                    exit_time = datetime.fromisoformat(str(exit_time_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.TAKE_PROFIT,
            timestamp=timestamp,
            layer_number=int(event_dict.get("layer_number", 0)),
            direction=str(event_dict.get("direction", "")),
            entry_price=entry_price,
            exit_price=exit_price,
            units=int(event_dict.get("units", 0)),
            pnl=pnl,
            pips=pips,
            entry_time=entry_time,
            exit_time=exit_time,
            retracement_count=int(event_dict.get("retracement_count", 0)),
        )


@dataclass
class AddLayerEvent(StrategyEvent):
    """Event for adding a new layer to the strategy.

    Attributes:
        layer_number: Layer number being added
        add_time: Time when layer was added

    Example:
        >>> event = AddLayerEvent(
        ...     event_type=EventType.ADD_LAYER,
        ...     layer_number=2,
        ...     add_time=datetime.now(),
        ... )
    """

    layer_number: int = 0
    add_time: datetime | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.ADD_LAYER

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["layer_number"] = self.layer_number
        if self.add_time:
            result["add_time"] = self.add_time.isoformat()
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "AddLayerEvent":
        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        add_time_raw = event_dict.get("add_time")
        add_time = None
        if add_time_raw:
            if isinstance(add_time_raw, datetime):
                add_time = add_time_raw
            else:
                try:
                    add_time = datetime.fromisoformat(str(add_time_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.ADD_LAYER,
            timestamp=timestamp,
            layer_number=int(event_dict.get("layer_number", 0)),
            add_time=add_time,
        )


@dataclass
class RemoveLayerEvent(StrategyEvent):
    """Event for removing a layer from the strategy.

    Attributes:
        layer_number: Layer number being removed
        add_time: Time when layer was originally added
        remove_time: Time when layer was removed

    Example:
        >>> event = RemoveLayerEvent(
        ...     event_type=EventType.REMOVE_LAYER,
        ...     layer_number=3,
        ...     add_time=datetime.now(),
        ...     remove_time=datetime.now(),
        ... )
    """

    layer_number: int = 0
    add_time: datetime | None = None
    remove_time: datetime | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.REMOVE_LAYER

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["layer_number"] = self.layer_number
        if self.add_time:
            result["add_time"] = self.add_time.isoformat()
        if self.remove_time:
            result["remove_time"] = self.remove_time.isoformat()
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "RemoveLayerEvent":
        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        add_time_raw = event_dict.get("add_time")
        add_time = None
        if add_time_raw:
            if isinstance(add_time_raw, datetime):
                add_time = add_time_raw
            else:
                try:
                    add_time = datetime.fromisoformat(str(add_time_raw))
                except (ValueError, TypeError):
                    pass

        remove_time_raw = event_dict.get("remove_time")
        remove_time = None
        if remove_time_raw:
            if isinstance(remove_time_raw, datetime):
                remove_time = remove_time_raw
            else:
                try:
                    remove_time = datetime.fromisoformat(str(remove_time_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.REMOVE_LAYER,
            timestamp=timestamp,
            layer_number=int(event_dict.get("layer_number", 0)),
            add_time=add_time,
            remove_time=remove_time,
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
        ...     timestamp=datetime.now(),
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

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.VOLATILITY_LOCK,
            timestamp=timestamp,
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
        ...     timestamp=datetime.now(),
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

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        return cls(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=timestamp,
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
        ...     event_type=EventType.STRATEGY_SIGNAL,
        ...     timestamp=datetime.now(),
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
        event_type_str = event_dict.get("event_type", "")
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            # If not a valid EventType, use the string as-is
            event_type = event_type_str  # type: ignore

        timestamp_raw = event_dict.get("timestamp")
        timestamp = None
        if timestamp_raw:
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(str(timestamp_raw))
                except (ValueError, TypeError):
                    pass

        # Extract data (everything except event_type and timestamp)
        data = {k: v for k, v in event_dict.items() if k not in {"event_type", "timestamp"}}

        return cls(
            event_type=event_type,  # type: ignore
            timestamp=timestamp,
            data=data,
        )
