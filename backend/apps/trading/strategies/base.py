from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from apps.trading.dataclasses import ExecutionState, StrategyResult, StrategyState, Tick
    from apps.trading.enums import StrategyType as StrategyTypeEnum
    from apps.trading.models import StrategyConfigurations


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

    @staticmethod
    @abstractmethod
    def parse_config(strategy_config: "StrategyConfigurations") -> Any:
        """Parse StrategyConfig to strategy-specific config object.

        This method is called by the registry before instantiation to convert
        the StrategyConfig model into a typed configuration object.

        Args:
            strategy_config: StrategyConfig model instance

        Returns:
            Strategy-specific config object (e.g., FloorStrategyConfig)

        Example:
            >>> @staticmethod
            >>> def parse_config(strategy_config: StrategyConfig) -> FloorStrategyConfig:
            >>>     return FloorStrategyConfig.from_dict(strategy_config.config_dict)
        """
        raise NotImplementedError

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

    def deserialize_state(self, state_dict: dict[str, Any]) -> TStrategyState:
        """Deserialize strategy state from database dictionary.

        This method is called by the executor to convert the persisted
        dict state into the strategy's specific StrategyState implementation.

        Default implementation: Calls get_state_class().from_dict(state_dict)
        Override only if custom deserialization logic is needed.

        Args:
            state_dict: Dictionary containing strategy state from database

        Returns:
            Strategy-specific state object (e.g., FloorStrategyState)
        """
        state_class = self.get_state_class()
        if hasattr(state_class, "from_dict") and callable(getattr(state_class, "from_dict")):
            return state_class.from_dict(state_dict)  # type: ignore
        raise NotImplementedError(
            f"{state_class.__name__} must implement from_dict() or override deserialize_state()"
        )

    @abstractmethod
    def get_state_class(self) -> type[TStrategyState]:
        """Return the strategy state class.

        Returns:
            Strategy state class (e.g., FloorStrategyState)
        """
        raise NotImplementedError

    def serialize_state(self, state: TStrategyState) -> dict[str, Any]:
        """Serialize strategy state to dictionary for database persistence.

        Default implementation calls to_dict() on the state object.
        Override only if custom serialization logic is needed.

        Args:
            state: Strategy-specific state object

        Returns:
            Dictionary for JSON storage
        """
        if hasattr(state, "to_dict") and callable(getattr(state, "to_dict")):
            return state.to_dict()  # type: ignore
        raise NotImplementedError(
            f"{type(state).__name__} must implement to_dict() or override serialize_state()"
        )

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
