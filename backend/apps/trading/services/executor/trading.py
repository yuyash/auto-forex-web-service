"""apps.trading.services.executor.trading

TradingExecutor for running live trading against real-time market data.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from apps.trading.dataclasses import (
    ExecutionState,
    TradeData,
)
from apps.trading.enums import LogLevel
from apps.trading.events import (
    InitialEntryEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
)
from apps.trading.models import TaskExecution, TradingTask
from apps.trading.services.executor.base import BaseExecutor
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy

logger: Logger = getLogger(name=__name__)


class TradingExecutor(BaseExecutor):
    """Executor for live trading tasks.

    The TradingExecutor orchestrates the execution of live trading by:
     - Subscribing to real-time market data from OANDA
     - Processing ticks through a strategy
     - Executing real trades through the OANDA API
     - Managing execution state with persistence for resume-ability
     - Emitting events for tracking and monitoring
     - Tracking performance metrics in real-time
    """

    def __init__(
        self,
        *,
        data_source: TickDataSource,
        strategy: Strategy,
        trading_ops: Any,  # OandaService instance
        execution: TaskExecution,
        task: TradingTask,
    ) -> None:
        """Initialize the TradingExecutor.

        Args:
            data_source: TickDataSource instance that yields batches of ticks
            strategy: Strategy instance to execute
            trading_ops: OandaService instance for executing real trades
            execution: TaskExecution model instance
            task: TradingTask instance
        """
        self.task = task
        self.trading_ops = trading_ops

        # Extract initial balance from account
        initial_balance = Decimal(str(getattr(task.oanda_account, "balance", "0") or "0"))

        # Initialize base executor
        from apps.trading.dataclasses import EventContext

        super().__init__(
            data_source=data_source,
            strategy=strategy,
            execution=execution,
            event_context=EventContext(
                execution=execution,
                user=task.user,
                account=getattr(task, "oanda_account", None),
                instrument=task.instrument,
            ),
            initial_balance=initial_balance,
            task_name=f"trading_{task.pk}",
        )

    def _get_initial_balance(self) -> Decimal:
        """Get the initial balance for trading."""
        return Decimal(str(getattr(self.task.oanda_account, "balance", "0") or "0"))

    def _handle_strategy_event(self, event: StrategyEvent, state: ExecutionState) -> None:
        """Handle a strategy event.

        Processes events emitted by the strategy, emitting appropriate
        events and updating metrics. For live trading, executes real
        trades through the OANDA API.

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
            self._execute_open_trade(event)
            self.performance_tracker.on_trade_executed(is_opening=True)

        elif isinstance(event, TakeProfitEvent):
            # Closing a position
            self._execute_close_trade(event)
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

    def _execute_open_trade(self, event: InitialEntryEvent | RetracementEvent) -> None:
        """Execute a trade to open a position.

        Args:
            event: Strategy event containing trade details
        """
        if self.trading_ops is None:
            logger.warning("Trading operations not available, skipping trade execution")
            return

        try:
            from apps.market.services.oanda import MarketOrderRequest

            # Create market order request
            order_request = MarketOrderRequest(
                instrument=self.task.instrument,
                units=Decimal(str(event.units)),
                take_profit=getattr(event, "take_profit", None),
                stop_loss=getattr(event, "stop_loss", None),
            )

            # Execute the order
            order = self.trading_ops.create_market_order(order_request)

            direction_str = (
                event.direction if isinstance(event.direction, str) else event.direction.value
            )

            logger.info(
                f"Trade executed: {direction_str} {event.units} units "
                f"at {event.price} (order_id={order.order_id})"
            )

            # Log to execution
            self.execution.add_log(
                LogLevel.INFO,
                f"Trade opened: {direction_str} {event.units} units at {event.price}",
            )

        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            self.execution.add_log(LogLevel.ERROR, f"Trade execution failed: {e}")
            # Don't raise - allow strategy to continue

    def _execute_close_trade(self, event: TakeProfitEvent) -> None:
        """Execute a trade to close a position.

        Args:
            event: TakeProfitEvent containing close details
        """
        if self.trading_ops is None:
            logger.warning("Trading operations not available, skipping position close")
            return

        try:
            # Close position by creating opposite market order
            from apps.market.services.oanda import MarketOrderRequest

            # Opposite direction to close
            close_units = Decimal(str(-event.units))

            order_request = MarketOrderRequest(
                instrument=self.task.instrument,
                units=close_units,
            )

            # Execute the closing order
            order = self.trading_ops.create_market_order(order_request)

            logger.info(
                f"Position closed: {event.units} units at {event.exit_price} "
                f"(PnL: {event.pnl}, order_id={order.order_id})"
            )

            # Log to execution
            self.execution.add_log(
                LogLevel.INFO,
                f"Position closed: {event.units} units at {event.exit_price} (PnL: {event.pnl})",
            )

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            self.execution.add_log(LogLevel.ERROR, f"Position close failed: {e}")
            # Don't raise - allow strategy to continue
