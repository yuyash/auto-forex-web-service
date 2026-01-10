"""apps.trading.dataclasses

Core domain dataclasses for the trading system refactor.

This module contains dataclasses that represent the core domain concepts
used throughout the trading system, including execution state, events,
metrics, and control structures.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class ExecutionState:
    """Complete execution state for a running task.

    This dataclass encapsulates all the state needed to resume a task
    execution from where it left off. It includes strategy-specific state,
    account balance, open positions, and progress tracking.

    Attributes:
        strategy_state: Strategy-specific state dictionary
        current_balance: Current account balance
        open_positions: List of open position dictionaries
        ticks_processed: Number of ticks processed so far
        last_tick_timestamp: Timestamp of the last processed tick (ISO format)
        metrics: Current performance metrics dictionary

    Requirements: 4.1, 4.2, 4.3
    """

    strategy_state: dict[str, Any]
    current_balance: Decimal
    open_positions: list[dict[str, Any]]
    ticks_processed: int
    last_tick_timestamp: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventContext:
    """Context information for event emission.

    This dataclass provides the necessary context for emitting events
    during task execution. It identifies the execution, user, account,
    and instrument involved.

    Attributes:
        execution: TaskExecution instance
        user: User instance
        account: OandaAccount instance (optional, None for backtests)
        instrument: Trading instrument (e.g., "USD_JPY")

    Requirements: 1.1, 1.2, 1.3
    """

    execution: Any  # TaskExecution model instance
    user: Any  # User model instance
    account: Any | None  # OandaAccount model instance or None
    instrument: str


@dataclass
class PerformanceMetrics:
    """Current performance metrics for a running execution.

    This dataclass tracks real-time performance metrics that are updated
    as the execution progresses. These metrics are used for progress
    updates and live monitoring.

    Attributes:
        ticks_processed: Number of ticks processed
        trades_executed: Number of trades executed
        current_balance: Current account balance
        current_pnl: Current profit/loss (realized + unrealized)
        unrealized_pnl: Unrealized profit/loss from open positions
        open_positions: Number of open positions

    Requirements: 5.5, 13.1, 13.2
    """

    ticks_processed: int
    trades_executed: int
    current_balance: Decimal
    current_pnl: Decimal
    unrealized_pnl: Decimal
    open_positions: int


@dataclass
class TaskControl:
    """Control flags for task execution lifecycle.

    This dataclass provides flags that control the execution flow of a task.
    These flags are checked periodically during execution to handle stop
    and pause requests.

    Attributes:
        should_stop: Flag indicating the task should stop
        should_pause: Flag indicating the task should pause

    Requirements: 2.6, 10.5
    """

    should_stop: bool = False
    should_pause: bool = False


@dataclass
class Tick:
    """Market tick data point.

    This dataclass represents a single market data point containing
    price information for a trading instrument at a specific time.

    Attributes:
        instrument: Trading instrument (e.g., "USD_JPY")
        timestamp: ISO format timestamp string
        bid: Bid price as string
        ask: Ask price as string
        mid: Mid price as string

    Requirements: 9.2, 18.4
    """

    instrument: str
    timestamp: str
    bid: str
    ask: str
    mid: str


@dataclass
class StrategyContext:
    """Context provided to strategy methods.

    This dataclass provides the necessary context for strategy methods
    to make trading decisions. It includes current account state and
    instrument information.

    Attributes:
        current_balance: Current account balance
        open_positions: List of open position dictionaries
        instrument: Trading instrument (e.g., "USD_JPY")
        pip_size: Pip size for the instrument

    Requirements: 3.5
    """

    current_balance: Decimal
    open_positions: list[dict[str, Any]]
    instrument: str
    pip_size: Decimal
