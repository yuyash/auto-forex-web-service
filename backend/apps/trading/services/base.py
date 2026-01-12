from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from apps.trading.dataclasses import ExecutionState, StrategyResult, StrategyState, Tick
    from apps.trading.enums import StrategyType as StrategyTypeEnum


# Type variable for strategy state
TStrategyState = TypeVar("TStrategyState", bound="StrategyState")


class Strategy(ABC, Generic[TStrategyState]):
    """Runtime strategy interface used by executors."""

    instrument: str
    pip_size: Decimal
    config: Any  # Strategy-specific config dataclass (e.g., FloorStrategyConfig)

    def __init__(self, instrument: str, pip_size: Decimal, config: Any) -> None:
        """Initialize the strategy with instrument, pip_size, and parsed configuration.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for the instrument
            config: Parsed strategy configuration dataclass (e.g., FloorStrategyConfig)
        """
        self.instrument = instrument
        self.pip_size = pip_size
        self.config = config

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyTypeEnum:
        """Return the strategy type enum value.

        Returns:
            StrategyType: Strategy type identifier

        Example:
            >>> strategy.strategy_type
            StrategyType.FLOOR
        """
        raise NotImplementedError

    @abstractmethod
    def on_tick(
        self, *, tick: Tick, state: ExecutionState[TStrategyState]
    ) -> StrategyResult[TStrategyState]:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state (typed with strategy state)

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        raise NotImplementedError

    @abstractmethod
    def initialize_strategy_state(self, state_dict: dict[str, Any]) -> TStrategyState:
        """Convert dict to strategy-specific state object.

        This method is called by the executor to convert the persisted
        dict state into the strategy's specific StrategyState implementation.

        Args:
            state_dict: Dictionary containing strategy state from persistence

        Returns:
            Strategy-specific state object (e.g., FloorStrategyState)
        """
        raise NotImplementedError

    def on_start(self, *, state: ExecutionState[TStrategyState]) -> StrategyResult[TStrategyState]:
        """Called when strategy starts.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        return StrategyResult.from_state(state)

    def on_resume(self, *, state: ExecutionState[TStrategyState]) -> StrategyResult[TStrategyState]:
        """Called when strategy resumes from a stopped state.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        return StrategyResult.from_state(state)

    def on_stop(self, *, state: ExecutionState[TStrategyState]) -> StrategyResult[TStrategyState]:
        """Called when strategy stops.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        return StrategyResult.from_state(state)
