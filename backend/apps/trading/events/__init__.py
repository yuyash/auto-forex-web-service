"""Trading events package.

This package contains typed event classes for strategy events.
"""

from .base import (
    AddLayerEvent,
    ClosePositionEvent,
    GenericStrategyEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    OpenPositionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
    VolatilityHedgeNeutralizeEvent,
    VolatilityLockEvent,
    register_event,
)

__all__ = [
    "AddLayerEvent",
    "ClosePositionEvent",
    "GenericStrategyEvent",
    "InitialEntryEvent",
    "MarginProtectionEvent",
    "OpenPositionEvent",
    "RemoveLayerEvent",
    "RetracementEvent",
    "StrategyEvent",
    "TakeProfitEvent",
    "VolatilityHedgeNeutralizeEvent",
    "VolatilityLockEvent",
    "register_event",
]
