"""apps.trading.services.executor.backtest

BacktestExecutor for running backtests against historical data.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import (
    ExecutionState,
    TradeData,
)
from apps.trading.events import (
    InitialEntryEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
)
from apps.trading.models import BacktestTask, TaskExecution
from apps.trading.services.executor.base import BaseExecutor
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy

logger: Logger = getLogger(name=__name__)


class BacktestExecutor(BaseExecutor):
    """Executor for backtest tasks.

    The BacktestExecutor orchestrates the execution of a backtest by:
     - Loading historical tick data from a data source
     - Processing ticks through a strategy in chronological order
     - Managing execution state with persistence for resume-ability
     - Emitting events for tracking and monitoring
     - Tracking performance metrics in real-time
    """

    def __init__(
        self,
        *,
        data_source: TickDataSource,
        strategy: Strategy,
        execution: TaskExecution,
        task: BacktestTask,
    ) -> None:
        """Initialize the BacktestExecutor.

        Args:
            data_source: TickDataSource instance that yields batches of ticks
            strategy: Strategy instance to execute
            execution: TaskExecution model instance
            task: BacktestTask instance
        """
        self.task = task

        # Initialize base executor with pip_size from task
        from apps.trading.dataclasses import EventContext

        super().__init__(
            data_source=data_source,
            strategy=strategy,
            execution=execution,
            event_context=EventContext(
                execution=execution,
                user=task.user,
                account=None,  # No account for backtests
                instrument=task.instrument,
            ),
            initial_balance=task.initial_balance,
            task_name=f"backtest_{task.pk}",
        )

    def _get_initial_balance(self) -> Decimal:
        """Get the initial balance for backtest."""
        return self.task.initial_balance

    def _handle_strategy_event(self, event: StrategyEvent, state: ExecutionState) -> None:
        """Handle a strategy event.

        Processes events emitted by the strategy, emitting appropriate
        events and updating metrics.

        Args:
            event: Strategy event object (typed subclass)
            state: Current execution state
        """
        # Emit strategy event
        self.event_emitter.emit_strategy_event(
            event=event,
            strategy_type=self.strategy.strategy_type,
        )

        # Handle trade events using type-safe pattern matching
        if isinstance(event, (InitialEntryEvent, RetracementEvent)):
            # Opening a position
            self.performance_tracker.on_trade_executed(is_opening=True)

        elif isinstance(event, TakeProfitEvent):
            # Closing a position
            self.performance_tracker.on_trade_executed(
                pnl=event.pnl,
                is_opening=False,
            )

            # Emit trade executed event
            trade = TradeData(
                direction=event.direction,
                units=event.units,
                entry_price=event.entry_price,
                exit_price=event.exit_price,
                pnl=event.pnl,
                pips=event.pips,
                timestamp=event.timestamp,
            )
            self.event_emitter.emit_trade_executed(trade)
