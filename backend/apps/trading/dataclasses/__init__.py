"""Trading dataclasses package.

This package contains dataclasses that represent the core domain concepts
used throughout the trading system.
"""

from apps.trading.dataclasses.context import EventContext, StrategyContext
from apps.trading.dataclasses.control import TaskControl
from apps.trading.dataclasses.metrics import ExecutionMetrics
from apps.trading.dataclasses.protocols import StrategyState, TStrategyState
from apps.trading.dataclasses.result import StrategyResult
from apps.trading.dataclasses.tick import Tick
from apps.trading.dataclasses.trade import OpenPosition, TradeData
from apps.trading.dataclasses.validation import ValidationResult

__all__ = [
    # Context
    "EventContext",
    "StrategyContext",
    # Control
    "TaskControl",
    # Metrics
    "ExecutionMetrics",
    # Protocols
    "StrategyState",
    "TStrategyState",
    # Result
    "StrategyResult",
    # Tick
    "Tick",
    # Trade
    "OpenPosition",
    "TradeData",
    # Validation
    "ValidationResult",
]
