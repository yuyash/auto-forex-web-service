"""apps.trading.dataclasses

Core domain dataclasses for the trading system refactor.

This module contains dataclasses that represent the core domain concepts
used throughout the trading system, including execution state, events,
metrics, and control structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.market.models import OandaAccount
    from apps.trading.events import StrategyEvent
    from apps.trading.models import TaskExecution


# ============================================================================
# TYPE VARIABLES
# ============================================================================


TStrategyState = TypeVar("TStrategyState", bound="StrategyState")


# ============================================================================
# PROTOCOLS
# ============================================================================


class StrategyState(Protocol):
    """Protocol for strategy-specific state.

    All strategy state classes must implement this protocol to ensure
    they can be properly serialized and deserialized.

    Example:
        >>> @dataclass
        ... class MyStrategyState:
        ...     value: int
        ...
        ...     def to_dict(self) -> dict[str, Any]:
        ...         return {"value": self.value}
        ...
        ...     @staticmethod
        ...     def from_dict(data: dict[str, Any]) -> MyStrategyState:
        ...         return MyStrategyState(value=data.get("value", 0))
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary format for serialization.

        Returns:
            dict: Dictionary representation of the state
        """
        ...

    @staticmethod
    def from_dict(data: dict[str, Any]) -> StrategyState:
        """Create state from dictionary.

        Args:
            data: Dictionary containing state data

        Returns:
            StrategyState: State instance
        """
        ...


@dataclass
class ValidationResult:
    """Result of a validation operation.

    This dataclass represents the outcome of validating data, providing
    a type-safe way to return validation results with optional error messages.
    """

    is_valid: bool
    error_message: str | None = None

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result.

        Returns:
            ValidationResult: Result indicating validation passed
        """
        return cls(is_valid=True, error_message=None)

    @classmethod
    def failure(cls, error_message: str) -> "ValidationResult":
        """Create a failed validation result.

        Args:
            error_message: Description of the validation error

        Returns:
            ValidationResult: Result indicating validation failed
        """
        return cls(is_valid=False, error_message=error_message)


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
    timestamp: str | None = None

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
            "timestamp": self.timestamp,
        }
        """Convert to dictionary format.

        Returns:
            Dictionary representation of the trade data
        """
        result = {
            "direction": self.direction,
            "units": self.units,
            "entry_price": self.entry_price,
        }

        if self.exit_price is not None:
            result["exit_price"] = self.exit_price
        if self.pnl is not None:
            result["pnl"] = self.pnl
        if self.pips is not None:
            result["pips"] = self.pips
        if self.order_id is not None:
            result["order_id"] = self.order_id
        if self.position_id is not None:
            result["position_id"] = self.position_id
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp

        return result


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


@dataclass
class ExecutionMetrics:
    """Performance metrics for a running execution.

    Tracks real-time performance metrics during task execution.
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    total_pips: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pips: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format.

        Returns:
            dict: Dictionary representation with Decimal values converted to strings
        """
        result = {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": str(self.total_pnl),
            "total_pips": str(self.total_pips),
            "max_drawdown": str(self.max_drawdown),
            "max_drawdown_pips": str(self.max_drawdown_pips),
            "win_rate": str(self.win_rate),
            "average_win": str(self.average_win),
            "average_loss": str(self.average_loss),
            "profit_factor": str(self.profit_factor),
        }
        if self.sharpe_ratio is not None:
            result["sharpe_ratio"] = str(self.sharpe_ratio)
        return result

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ExecutionMetrics":
        """Create ExecutionMetrics from dictionary.

        Args:
            data: Dictionary containing metrics data

        Returns:
            ExecutionMetrics: ExecutionMetrics instance
        """
        sharpe_ratio = data.get("sharpe_ratio")
        return ExecutionMetrics(
            total_trades=int(data.get("total_trades", 0)),
            winning_trades=int(data.get("winning_trades", 0)),
            losing_trades=int(data.get("losing_trades", 0)),
            total_pnl=Decimal(str(data.get("total_pnl", "0"))),
            total_pips=Decimal(str(data.get("total_pips", "0"))),
            max_drawdown=Decimal(str(data.get("max_drawdown", "0"))),
            max_drawdown_pips=Decimal(str(data.get("max_drawdown_pips", "0"))),
            win_rate=Decimal(str(data.get("win_rate", "0"))),
            average_win=Decimal(str(data.get("average_win", "0"))),
            average_loss=Decimal(str(data.get("average_loss", "0"))),
            profit_factor=Decimal(str(data.get("profit_factor", "0"))),
            sharpe_ratio=Decimal(str(sharpe_ratio)) if sharpe_ratio is not None else None,
        )


@dataclass
class ExecutionState(Generic[TStrategyState]):
    """Complete execution state for a running task.

    This dataclass encapsulates all the state needed to resume a task
    execution from where it left off. It includes strategy-specific state,
    account balance, open positions, and progress tracking.

    Generic over TStrategyState to provide type-safe strategy state access.

    Attributes:
        strategy_state: Strategy-specific state (typed via Generic)
        current_balance: Current account balance
        open_positions: List of open positions
        ticks_processed: Number of ticks processed so far
        last_tick_timestamp: Timestamp of the last processed tick (ISO format)
        metrics: Current performance metrics

    Requirements: 4.1, 4.2, 4.3

    Example:
        >>> state: ExecutionState[FloorStrategyState] = ExecutionState(
        ...     strategy_state=FloorStrategyState(),
        ...     current_balance=Decimal("10000"),
        ...     open_positions=[],
        ...     ticks_processed=0,
        ... )
        >>> # Now state.strategy_state is typed as FloorStrategyState!
    """

    strategy_state: TStrategyState
    current_balance: Decimal
    open_positions: list[OpenPosition]
    ticks_processed: int
    last_tick_timestamp: str | None = None
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    def copy_with(self, **changes: Any) -> "ExecutionState[TStrategyState]":
        """Create a copy of this state with specified changes.

        Args:
            **changes: Fields to update in the copy

        Returns:
            ExecutionState: New instance with updated fields

        Example:
            >>> new_state = state.copy_with(ticks_processed=100)
        """
        from dataclasses import replace

        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for serialization.

        Returns:
            dict: Dictionary representation
        """
        return {
            "strategy_state": self.strategy_state.to_dict(),
            "current_balance": str(self.current_balance),
            "open_positions": [pos.to_dict() for pos in self.open_positions],
            "ticks_processed": self.ticks_processed,
            "last_tick_timestamp": self.last_tick_timestamp,
            "metrics": self.metrics.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ExecutionState":
        """Create ExecutionState from dictionary.

        Note: strategy_state is returned as a dict. The caller is responsible
        for converting it to the appropriate StrategyState implementation
        using the strategy's from_dict method.

        Args:
            data: Dictionary containing execution state data

        Returns:
            ExecutionState: ExecutionState instance with strategy_state as dict
        """
        # Parse positions
        positions_data = data.get("open_positions", [])
        positions = [
            OpenPosition.from_dict(pos_data)
            for pos_data in positions_data
            if isinstance(pos_data, dict)
        ]

        # Parse metrics
        metrics_data = data.get("metrics", {})
        metrics = (
            ExecutionMetrics.from_dict(metrics_data)
            if isinstance(metrics_data, dict)
            else ExecutionMetrics()
        )

        # Note: strategy_state is kept as dict here.
        # The strategy implementation should convert it using its from_dict method.
        return ExecutionState(
            strategy_state=data.get("strategy_state", {}),  # type: ignore[arg-type]
            current_balance=Decimal(str(data.get("current_balance", "0"))),
            open_positions=positions,
            ticks_processed=int(data.get("ticks_processed", 0)),
            last_tick_timestamp=data.get("last_tick_timestamp"),
            metrics=metrics,
        )


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

    execution: "TaskExecution"  # Forward reference to avoid circular import
    user: "User"  # Forward reference to avoid circular import
    account: "OandaAccount | None"  # Forward reference to avoid circular import
    instrument: str


@dataclass
class TaskControl:
    """Control flags for task execution lifecycle.

    This dataclass provides flags that control the execution flow of a task.
    These flags are checked periodically during execution to handle stop requests.

    Attributes:
        should_stop: Flag indicating the task should stop

    Requirements: 2.6, 10.5
    """

    should_stop: bool = False


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
        mid: Mid price as Decimal

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


@dataclass
class StrategyContext:
    """Context provided to strategy methods.

    This dataclass provides the necessary context for strategy methods
    to make trading decisions. It includes current account state and
    instrument information.

    Attributes:
        current_balance: Current account balance
        open_positions: List of open positions
        instrument: Trading instrument (e.g., "USD_JPY")
        pip_size: Pip size for the instrument

    Requirements: 3.5
    """

    current_balance: Decimal
    open_positions: list[OpenPosition]
    instrument: str
    pip_size: Decimal


@dataclass
class StrategyResult(Generic[TStrategyState]):
    """Result returned by strategy lifecycle methods.

    This dataclass encapsulates the result of strategy operations,
    providing a type-safe way to return updated state and events.

    Generic over TStrategyState to maintain type safety with ExecutionState.

    Attributes:
        state: Updated execution state after processing
        events: List of strategy events emitted during processing

    Requirements: 3.1, 3.2

    Example:
        >>> from apps.trading.events import StrategyStartedEvent
        >>> result: StrategyResult[FloorStrategyState] = StrategyResult(
        ...     state=updated_state,
        ...     events=[StrategyStartedEvent(timestamp="2024-01-01T00:00:00Z")]
        ... )
    """

    state: ExecutionState[TStrategyState]
    events: list[StrategyEvent] = field(default_factory=list)

    @classmethod
    def from_state(cls, state: ExecutionState[TStrategyState]) -> "StrategyResult[TStrategyState]":
        """Create a result with only state, no events.

        Args:
            state: Execution state to return

        Returns:
            StrategyResult: Result with state and empty events list
        """
        return cls(state=state, events=[])

    @classmethod
    def with_events(
        cls, state: ExecutionState[TStrategyState], events: list[StrategyEvent]
    ) -> "StrategyResult[TStrategyState]":
        """Create a result with state and events.

        Args:
            state: Execution state to return
            events: List of strategy events

        Returns:
            StrategyResult: Result with state and events
        """
        return cls(state=state, events=events)
