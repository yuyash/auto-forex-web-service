"""apps.trading.services.executor.backtest

BacktestExecutor for running backtests against historical data.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from apps.trading.dataclasses import (
    ExecutionState,
    Tick,
    TradeData,
)
from apps.trading.events import (
    InitialEntryEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
)
from apps.trading.services.errors import ErrorAction, ErrorContext, ErrorHandler
from apps.trading.services.executor.base import BaseExecutor
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy

if TYPE_CHECKING:
    from apps.trading.models import BacktestTasks, Executions

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
        execution: Executions,
        task: BacktestTasks,
    ) -> None:
        """Initialize the BacktestExecutor.

        Args:
            data_source: TickDataSource instance that yields batches of ticks
            strategy: Strategy instance to execute
            execution: TaskExecution model instance
            task: BacktestTask instance
        """
        self.task = task

        # Store time range for progress calculation
        self.start_time = task.start_time
        self.end_time = task.end_time

        # Initialize error handler
        self.error_handler = ErrorHandler()

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

    def _calculate_progress(self, current_tick: Tick) -> int:
        """Calculate progress percentage based on current tick timestamp.

        Args:
            current_tick: Current tick being processed

        Returns:
            Progress percentage (0-100)
        """
        try:
            # Convert timestamps to comparable format
            from datetime import datetime

            if isinstance(current_tick.timestamp, str):
                current_time = datetime.fromisoformat(current_tick.timestamp.replace("Z", "+00:00"))
            else:
                current_time = current_tick.timestamp

            # Calculate time-based progress
            total_duration = (self.end_time - self.start_time).total_seconds()
            elapsed_duration = (current_time - self.start_time).total_seconds()

            if total_duration <= 0:
                return 0

            progress = int((elapsed_duration / total_duration) * 100)
            return max(0, min(99, progress))  # Cap at 99% until completion

        except Exception as e:
            logger.warning(f"Failed to calculate progress: {e}")
            # Fallback to current progress
            return self.execution.progress

    def _process_tick(self, tick: Tick, state: ExecutionState) -> ExecutionState:
        """Process a single tick through the strategy with error handling.

        Args:
            tick: Tick to process
            state: Current execution state

        Returns:
            ExecutionState: Updated execution state
        """
        try:
            # Call parent implementation
            return super()._process_tick(tick, state)

        except Exception as e:
            # Create error context
            error_context = ErrorContext(
                error=e,
                execution_id=self.execution.pk,
                task_id=self.task.pk,
                tick_data={
                    "instrument": tick.instrument,
                    "timestamp": str(tick.timestamp),
                    "bid": str(tick.bid),
                    "ask": str(tick.ask),
                },
                strategy_state=state.strategy_state.to_dict()
                if hasattr(state.strategy_state, "to_dict")
                else {},
                additional_info={
                    "ticks_processed": state.ticks_processed,
                    "current_balance": str(state.current_balance),
                },
            )

            # Determine action based on error type
            action = self.error_handler.handle_error(e, error_context)

            # Emit error event
            self.event_emitter.emit_error(
                e,
                error_context={
                    "tick": error_context.tick_data,
                    "ticks_processed": state.ticks_processed,
                    "action": action.value,
                },
            )

            # Take appropriate action
            if action == ErrorAction.FAIL_TASK:
                logger.critical(f"Critical error in tick processing: {e}")
                raise
            elif action == ErrorAction.RETRY:
                logger.warning(f"Transient error in tick processing, will retry: {e}")
                # For now, we'll just continue - retry logic would be more complex
                # and might require changes to the data source
                return state
            elif action == ErrorAction.LOG_AND_CONTINUE:
                logger.error(f"Error in tick processing, continuing: {e}")
                return state
            else:  # ErrorAction.REJECT
                logger.error(f"Validation error in tick processing: {e}")
                raise

    def _handle_strategy_event(self, event: StrategyEvent, state: ExecutionState) -> None:
        """Handle a strategy event.

        Processes events emitted by the strategy, emitting appropriate
        events and updating metrics.

        Args:
            event: Strategy event object (typed subclass)
            state: Current execution state
        """
        logger.debug(f"Handling strategy event: {type(event).__name__}")

        # Emit strategy event
        self.event_emitter.emit_strategy_event(
            event=event,
            strategy_type=self.strategy.strategy_type,
        )
        logger.debug(f"Emitted strategy event: {type(event).__name__}")

        # Handle trade events using type-safe pattern matching
        if isinstance(event, (InitialEntryEvent, RetracementEvent)):
            logger.debug("Trade event: opening position")
            # Opening a position
            self.performance_tracker.on_trade_executed(is_opening=True)

        elif isinstance(event, TakeProfitEvent):
            logger.debug(f"Trade event: closing position with PnL={event.pnl}")
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
