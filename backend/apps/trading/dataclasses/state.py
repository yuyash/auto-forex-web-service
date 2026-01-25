"""State-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Generic

from .metrics import ExecutionMetrics
from .protocols import TStrategyState
from .trade import OpenPosition

if TYPE_CHECKING:
    pass


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
        equity_curve: Time series of balance snapshots
        trades: List of completed trades
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
    equity_curve: list[dict[str, str]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)

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
            "equity_curve": self.equity_curve,
            "trades": self.trades,
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

        # Parse equity curve
        equity_curve = data.get("equity_curve", [])
        if not isinstance(equity_curve, list):
            equity_curve = []

        # Parse trades
        trades = data.get("trades", [])
        if not isinstance(trades, list):
            trades = []

        # Note: strategy_state is kept as dict here.
        # The strategy implementation should convert it using its from_dict method.
        return ExecutionState(
            strategy_state=data.get("strategy_state", {}),  # type: ignore[arg-type]
            current_balance=Decimal(str(data.get("current_balance", "0"))),
            open_positions=positions,
            ticks_processed=int(data.get("ticks_processed", 0)),
            last_tick_timestamp=data.get("last_tick_timestamp"),
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
        )
