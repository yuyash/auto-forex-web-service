"""Trading events package.

This package contains typed event classes for strategy events.
"""

from .base import (
    AddLayerEvent,
    GenericStrategyEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
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
    "GenericStrategyEvent",
    "InitialEntryEvent",
    "MarginProtectionEvent",
    "RemoveLayerEvent",
    "RetracementEvent",
    "StrategyEvent",
    "TakeProfitEvent",
    "VolatilityHedgeNeutralizeEvent",
    "VolatilityLockEvent",
    "register_event",
]
