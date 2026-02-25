from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.trading.dataclasses import EventExecutionResult, StrategyResult, Tick
    from apps.trading.events.handler import EventHandler
    from apps.trading.order import OrderService
    from apps.trading.enums import StrategyType as StrategyTypeEnum
    from apps.trading.models import StrategyConfiguration
    from apps.trading.models.state import ExecutionState


class Strategy(ABC):
    """Runtime strategy interface used by executors."""

    instrument: str
    pip_size: Decimal
    account_currency: str
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
        self.account_currency = ""
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

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        """Normalize untrusted API payload into canonical strategy parameters."""
        return dict(parameters)

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        """Return default strategy parameters."""
        return {}

    @classmethod
    def validate_parameters(
        cls,
        *,
        parameters: dict[str, Any],
        config_schema: dict[str, Any] | None = None,
    ) -> None:
        """Validate parameters against schema and strategy rules.

        Raises:
            ValueError: If parameters are invalid.
        """
        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a JSON object")

        if config_schema:
            from jsonschema import ValidationError as JsonSchemaValidationError
            from jsonschema import validate

            payload = cls._to_schema_primitives(parameters)
            try:
                validate(instance=payload, schema=config_schema)
            except JsonSchemaValidationError as exc:
                raise ValueError(exc.message) from exc

    @classmethod
    def _to_schema_primitives(cls, value: Any) -> Any:
        """Convert rich Python types into JSON-schema friendly primitives."""
        if isinstance(value, Decimal):
            integral = value.to_integral_value()
            return int(integral) if value == integral else float(value)
        if isinstance(value, dict):
            return {k: cls._to_schema_primitives(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._to_schema_primitives(v) for v in value]
        if isinstance(value, tuple):
            return [cls._to_schema_primitives(v) for v in value]
        return value

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

    def create_event_handler(
        self, *, order_service: "OrderService", instrument: str
    ) -> "EventHandler":
        """Create event handler used by the executor."""
        from apps.trading.events.handler import EventHandler

        return EventHandler(order_service, instrument)

    def apply_event_execution_result(
        self,
        *,
        state: "ExecutionState",
        execution_result: "EventExecutionResult",
    ) -> None:
        """Apply order execution feedback to strategy state."""
        _ = state
        _ = execution_result
