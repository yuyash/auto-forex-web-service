"""Result-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.events import StrategyEvent
    from apps.trading.models.state import ExecutionState


@dataclass
class StrategyResult:
    """Result returned by strategy lifecycle methods.

    This dataclass encapsulates the result of strategy operations,
    providing a way to return updated state and events.

    Attributes:
        state: Updated execution state after processing
        events: List of strategy events emitted during processing
    """

    state: ExecutionState
    events: list[StrategyEvent] = field(default_factory=list)

    @classmethod
    def from_state(cls, state: ExecutionState) -> "StrategyResult":
        """Create a result with only state, no events.

        Args:
            state: Execution state to return

        Returns:
            StrategyResult: Result with state and empty events list
        """
        return cls(state=state, events=[])

    @classmethod
    def with_events(cls, state: ExecutionState, events: list[StrategyEvent]) -> "StrategyResult":
        """Create a result with state and events.

        Args:
            state: Execution state to return
            events: List of strategy events

        Returns:
            StrategyResult: Result with state and events
        """
        return cls(state=state, events=events)
