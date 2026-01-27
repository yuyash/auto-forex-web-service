from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.trading.dataclasses import StrategyResult, Tick
    from apps.trading.enums import StrategyType as StrategyTypeEnum
    from apps.trading.models import StrategyConfiguration
    from apps.trading.models.state import ExecutionState


class Strategy(ABC):
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
    def parse_config(strategy_config: "StrategyConfiguration") -> Any:
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
    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        raise NotImplementedError

    def deserialize_state(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Deserialize strategy state from database dictionary.

        This method is called by the executor to convert the persisted
        dict state into the strategy's specific state format.

        Args:
            state_dict: Dictionary containing strategy state from database

        Returns:
            Strategy-specific state dictionary
        """
        return state_dict

    def serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Serialize strategy state to dictionary for database persistence.

        Args:
            state: Strategy-specific state dictionary

        Returns:
            Dictionary for JSON storage
        """
        return state

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy starts.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        from apps.trading.dataclasses import StrategyResult

        return StrategyResult(state=state, events=[])

    def on_resume(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy resumes from a stopped state.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        from apps.trading.dataclasses import StrategyResult

        return StrategyResult(state=state, events=[])

    def on_stop(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy stops.

        Args:
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        from apps.trading.dataclasses import StrategyResult

        return StrategyResult(state=state, events=[])
