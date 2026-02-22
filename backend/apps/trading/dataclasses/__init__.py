"""Trading dataclasses package.

This package contains dataclasses that represent the core domain concepts
used throughout the trading system.
"""

from apps.trading.dataclasses.context import EventContext
from apps.trading.dataclasses.control import TaskControl
from apps.trading.dataclasses.protocols import StrategyState, TStrategyState
from apps.trading.dataclasses.result import StrategyResult
from apps.trading.dataclasses.tick import Tick

__all__ = [
    # Context
    "EventContext",
    # Control
    "TaskControl",
    # Protocols
    "StrategyState",
    "TStrategyState",
    # Result
    "StrategyResult",
    # Tick
    "Tick",
]
