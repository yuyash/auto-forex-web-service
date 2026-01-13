"""Protocol definitions for trading dataclasses."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

TStrategyState = TypeVar("TStrategyState", bound="StrategyState")


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
