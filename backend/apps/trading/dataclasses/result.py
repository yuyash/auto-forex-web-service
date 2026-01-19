"""Result-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic

from .protocols import TStrategyState
from .state import ExecutionState

if TYPE_CHECKING:
    from apps.trading.events import StrategyEvent


@dataclass
class StrategyResult(Generic[TStrategyState]):
    """Result returned by strategy lifecycle methods.

    This dataclass encapsulates the result of strategy operations,
    providing a type-safe way to return updated state and events.

    Generic over TStrategyState to maintain type safety with ExecutionState.

    Attributes:
        state: Updated execution state after processing
        events: List of strategy events emitted during processing
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
