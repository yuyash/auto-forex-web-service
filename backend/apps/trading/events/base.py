"""Typed event classes for strategy events.

This module provides type-safe event classes for each EventType, making
it clear what fields are required for each event and enabling better
IDE support and compile-time checking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.trading.enums import EventType

if TYPE_CHECKING:
    from apps.trading.dataclasses.context import EventContext


@dataclass
class StrategyEvent(ABC):
    """Base class for all strategy events.

    This is the abstract base class that all specific event types inherit from.
    It provides common fields and methods shared by all events.

    Attributes:
        event_type: Type of event (EventType enum value)
        timestamp: Event timestamp (optional)"""

    event_type: EventType
    timestamp: datetime | None = None

    @abstractmethod
    def activate(self, context: "EventContext") -> None:
        """Execute event-specific logic.

        This method is called by the EventExecutor to perform the actions
        associated with this event. Each event type implements its own
        activation logic (e.g., opening positions, closing positions, logging).

        Args:
            context: Event context containing task, account, instrument info

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement activate() method")

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
        elif event_type == EventType.VOLATILITY_HEDGE_NEUTRALIZE:
            return VolatilityHedgeNeutralizeEvent.from_dict(event_dict)
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

    def activate(self, context: "EventContext") -> None:
        """Execute initial entry event logic.

        This method logs the initial entry action at INFO level.
        The actual position ordering will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Initial entry: layer={self.layer_number}, direction={self.direction}, "
            f"price={self.price}, units={self.units}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "layer_number": self.layer_number,
                "direction": self.direction,
                "price": str(self.price),
                "units": self.units,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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

    def activate(self, context: "EventContext") -> None:
        """Execute retracement event logic.

        This method logs the retracement action at INFO level.
        The actual position addition will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Retracement: layer={self.layer_number}, direction={self.direction}, "
            f"price={self.price}, units={self.units}, count={self.retracement_count}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "layer_number": self.layer_number,
                "direction": self.direction,
                "price": str(self.price),
                "units": self.units,
                "retracement_count": self.retracement_count,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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

    def activate(self, context: "EventContext") -> None:
        """Execute take profit event logic.

        This method logs the take profit action at INFO level.
        The actual position closing will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Take profit: layer={self.layer_number}, direction={self.direction}, "
            f"entry={self.entry_price}, exit={self.exit_price}, units={self.units}, "
            f"pnl={self.pnl}, pips={self.pips}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "layer_number": self.layer_number,
                "direction": self.direction,
                "entry_price": str(self.entry_price),
                "exit_price": str(self.exit_price),
                "units": self.units,
                "pnl": str(self.pnl),
                "pips": str(self.pips),
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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

    def activate(self, context: "EventContext") -> None:
        """Execute add layer event logic.

        This method logs the add layer action at INFO level.
        The actual layer creation will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Add layer: layer_number={self.layer_number}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "layer_number": self.layer_number,
                "add_time": self.add_time.isoformat() if self.add_time else None,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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

    def activate(self, context: "EventContext") -> None:
        """Execute remove layer event logic.

        This method logs the remove layer action at INFO level.
        The actual layer closing will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Remove layer: layer_number={self.layer_number}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "layer_number": self.layer_number,
                "add_time": self.add_time.isoformat() if self.add_time else None,
                "remove_time": self.remove_time.isoformat() if self.remove_time else None,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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

    def activate(self, context: "EventContext") -> None:
        """Execute volatility lock event logic.

        This method logs the volatility lock action at INFO level.
        The actual position closing will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Volatility lock: reason={self.reason}, atr={self.atr_value}, threshold={self.threshold}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "reason": self.reason,
                "atr_value": str(self.atr_value) if self.atr_value else None,
                "threshold": str(self.threshold) if self.threshold else None,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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
class VolatilityHedgeNeutralizeEvent(StrategyEvent):
    """Event emitted when hedging-mode volatility lock neutralizes positions.

    Instead of closing all positions, this event instructs the handler to open
    opposite hedge positions for each existing open position so that the net
    exposure becomes zero.  The strategy then pauses until volatility subsides.

    Attributes:
        reason: Human-readable description of why the neutralization was triggered.
        atr_value: Current ATR value that triggered the event.
        threshold: ATR threshold that was exceeded.
        hedge_instructions: List of dicts describing each hedge to open.
            Each dict contains: ``direction``, ``units``, ``layer_index``,
            ``source_entry_id``.
    """

    reason: str = ""
    atr_value: Decimal | None = None
    threshold: Decimal | None = None
    hedge_instructions: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.VOLATILITY_HEDGE_NEUTRALIZE

    def activate(self, context: "EventContext") -> None:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "Volatility hedge neutralize: reason=%s, hedges=%d",
            self.reason,
            len(self.hedge_instructions),
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["reason"] = self.reason
        if self.atr_value is not None:
            result["atr_value"] = str(self.atr_value)
        if self.threshold is not None:
            result["threshold"] = str(self.threshold)
        result["hedge_instructions"] = self.hedge_instructions
        return result

    @classmethod
    def from_dict(cls, event_dict: dict[str, Any]) -> "VolatilityHedgeNeutralizeEvent":
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
            event_type=EventType.VOLATILITY_HEDGE_NEUTRALIZE,
            timestamp=timestamp,
            reason=str(event_dict.get("reason", "")),
            atr_value=atr_value,
            threshold=threshold,
            hedge_instructions=list(event_dict.get("hedge_instructions", [])),
        )


@dataclass
class MarginProtectionEvent(StrategyEvent):
    """Event for margin protection triggered.

    Attributes:
        reason: Reason for margin protection
        current_margin: Current margin level (optional)
        threshold: Margin threshold (optional)
        positions_closed: Number of positions closed (optional)
        units_to_close: Number of units to close (optional)

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
    units_to_close: int | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = EventType.MARGIN_PROTECTION

    def activate(self, context: "EventContext") -> None:
        """Execute margin protection event logic.

        This method logs the margin protection action at INFO level.
        The actual position closing will be handled by the EventExecutor.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Margin protection: reason={self.reason}, current={self.current_margin}, "
            f"threshold={self.threshold}, closed={self.positions_closed}, "
            f"units_to_close={self.units_to_close}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "reason": self.reason,
                "current_margin": str(self.current_margin) if self.current_margin else None,
                "threshold": str(self.threshold) if self.threshold else None,
                "positions_closed": self.positions_closed,
                "units_to_close": self.units_to_close,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["reason"] = self.reason
        if self.current_margin is not None:
            result["current_margin"] = str(self.current_margin)
        if self.threshold is not None:
            result["threshold"] = str(self.threshold)
        if self.positions_closed is not None:
            result["positions_closed"] = self.positions_closed
        if self.units_to_close is not None:
            result["units_to_close"] = self.units_to_close
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
            units_to_close=event_dict.get("units_to_close"),
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

    def activate(self, context: "EventContext") -> None:
        """Execute generic event logic.

        For generic events, this logs the event at an appropriate level based on event type.
        Lifecycle events log at INFO or DEBUG, error events at WARNING or ERROR.

        Args:
            context: Event context containing task, account, instrument info
        """
        import logging

        logger = logging.getLogger(__name__)

        # Determine log level based on event type
        from apps.trading.enums import EventType

        if self.event_type == EventType.TICK_RECEIVED:
            log_level = logging.DEBUG
        elif self.event_type in {
            EventType.STRATEGY_STARTED,
            EventType.STRATEGY_PAUSED,
            EventType.STRATEGY_RESUMED,
            EventType.STRATEGY_STOPPED,
        }:
            log_level = logging.INFO
        elif self.event_type == EventType.STATUS_CHANGED:
            log_level = logging.WARNING
        elif self.event_type == EventType.ERROR_OCCURRED:
            log_level = logging.ERROR
        else:
            log_level = logging.INFO

        logger.log(
            log_level,
            f"Event: {self.event_type.value}",
            extra={
                "task_id": str(context.task_id),
                "task_type": context.task_type.value,
                "instrument": context.instrument,
                "event_type": self.event_type.value,
                "event_data": self.data,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
        )

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
            event_type = event_type_str

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
            event_type=event_type,
            timestamp=timestamp,
            data=data,
        )
