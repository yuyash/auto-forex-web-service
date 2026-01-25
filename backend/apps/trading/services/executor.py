"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Generic

from apps.trading.dataclasses import (
    EventContext,
    ExecutionState,
)
from apps.trading.dataclasses.protocols import TStrategyState
from apps.trading.events import StrategyEvent
from apps.trading.services.controller import TaskController
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy

if TYPE_CHECKING:
    from apps.trading.models import BacktestTasks, TradingTasks

logger = logging.getLogger(__name__)


class TaskExecutor(ABC, Generic[TStrategyState]):
    """Abstract base class for task execution.

    This class provides the core execution loop for processing ticks through
    a strategy, managing state, and handling lifecycle events.
    """

    def __init__(
        self,
        *,
        strategy: Strategy[TStrategyState],
        data_source: TickDataSource,
        controller: TaskController,
        event_context: EventContext,
        initial_balance: Decimal,
        instrument: str,
        pip_size: Decimal,
    ) -> None:
        """Initialize the executor.

        Args:
            strategy: Strategy instance to execute
            data_source: Tick data source
            controller: Task controller for lifecycle management
            event_context: Context for event emission
            initial_balance: Initial account balance
            instrument: Trading instrument
            pip_size: Pip size for the instrument
        """
        self.strategy = strategy
        self.data_source = data_source
        self.controller = controller
        self.event_context = event_context
        self.initial_balance = initial_balance
        self.instrument = instrument
        self.pip_size = pip_size

    @abstractmethod
    def load_state(self) -> ExecutionState[TStrategyState]:
        """Load execution state from storage.

        Returns:
            ExecutionState: Current execution state
        """
        ...

    @abstractmethod
    def save_state(self, state: ExecutionState[TStrategyState]) -> None:
        """Save execution state to storage.

        Args:
            state: Execution state to save
        """
        ...

    @abstractmethod
    def emit_events(self, events: list[StrategyEvent]) -> None:
        """Emit strategy events.

        Args:
            events: List of events to emit
        """
        ...

    def execute(self) -> None:
        """Execute the task.

        This is the main execution loop that:
        1. Loads initial state
        2. Calls strategy.on_start()
        3. Processes ticks through strategy.on_tick()
        4. Handles stop signals
        5. Calls strategy.on_stop()
        6. Saves final state
        """
        try:
            # Start controller
            self.controller.start()

            # Load state
            state = self.load_state()
            logger.info(
                f"Loaded state: balance={state.current_balance}, "
                f"positions={len(state.open_positions)}, "
                f"ticks_processed={state.ticks_processed}"
            )

            # Call on_start
            result = self.strategy.on_start(state=state)
            state = result.state
            self.emit_events(result.events)
            self.save_state(state)

            # Process ticks
            batch_count = 0
            for tick_batch in self.data_source:
                # Check for stop signal
                control = self.controller.check_control()
                if control.should_stop:
                    logger.info("Stop signal received, stopping execution")
                    break

                # Process each tick in batch
                for tick in tick_batch:
                    result = self.strategy.on_tick(tick=tick, state=state)
                    state = result.state
                    self.emit_events(result.events)

                    # Update metrics and trades from events
                    if result.events:
                        # TODO: Re-enable trade history and metrics tracking
                        # Build trades (persists to DB)
                        # new_trades = self.trade_history_builder.process_events(result.events)
                        # if new_trades:
                        #     trades = state.trades + new_trades
                        #     state = state.copy_with(trades=trades)

                        # Update metrics (persists to DB per minute)
                        # updated_metrics = self.metrics.update_metrics_from_events(
                        #     state.metrics,
                        #     result.events,
                        # )

                        # Check if balance changed (trade closed)
                        # balance_changed = updated_metrics.total_trades > state.metrics.total_trades

                        # state = state.copy_with(metrics=updated_metrics)

                        # Add equity point and persist if balance changed
                        # TODO: Re-enable equity tracking
                        # if balance_changed and tick.timestamp:
                        #     equity_point = {
                        #         "timestamp": tick.timestamp.isoformat(),
                        #         "balance": str(state.current_balance),
                        #     }
                        #     equity_curve = state.equity_curve + [equity_point]
                        #     state = state.copy_with(equity_curve=equity_curve)

                        #     # Persist equity point to database
                        #     self.equity_tracker.record_equity_point(
                        #         tick.timestamp,
                        #         state.current_balance,
                        #         state.ticks_processed,
                        #     )
                        pass

                    # Update tick count and timestamp
                    state = state.copy_with(
                        ticks_processed=state.ticks_processed + 1,
                        last_tick_timestamp=tick.timestamp.isoformat(),
                    )

                # Save state after each batch
                batch_count += 1
                self.save_state(state)

                # Send heartbeat
                if batch_count % 10 == 0:
                    self.controller.heartbeat(
                        status_message=f"Processed {state.ticks_processed} ticks"
                    )

            # Call on_stop
            result = self.strategy.on_stop(state=state)
            state = result.state
            self.emit_events(result.events)
            self.save_state(state)

            # Mark as stopped
            self.controller.stop(status_message="Execution completed successfully")
            logger.info(
                f"Execution completed: ticks_processed={state.ticks_processed}, "
                f"final_balance={state.current_balance}"
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            self.controller.stop(status_message=f"Execution failed: {e}", failed=True)
            raise
        finally:
            # Clean up data source
            try:
                self.data_source.close()
            except Exception as e:
                logger.warning(f"Failed to close data source: {e}")


class BacktestExecutor(TaskExecutor[TStrategyState]):
    """Executor for backtest tasks."""

    def __init__(
        self,
        *,
        task: BacktestTasks,
        strategy: Strategy[TStrategyState],
        data_source: TickDataSource,
        controller: TaskController,
    ) -> None:
        """Initialize the backtest executor.

        Args:
            task: Backtest task instance
            strategy: Strategy instance to execute
            data_source: Tick data source
            controller: Task controller for lifecycle management
        """
        self.task = task

        # Create event context
        event_context = EventContext(
            user=task.user,
            account=None,  # No account for backtests
            instrument=task.instrument,
        )

        super().__init__(
            strategy=strategy,
            data_source=data_source,
            controller=controller,
            event_context=event_context,
            initial_balance=task.initial_balance,
            instrument=task.instrument,
            pip_size=task._pip_size or Decimal("0.01"),
        )

        # Initialize services for data persistence
        from apps.trading.services.equity_tracker import EquityTracker
        from apps.trading.services.metrics import MetricsCalculator
        from apps.trading.services.trade_history_builder import TradeHistoryBuilder

        celery_task_id = task.celery_task_id or ""
        self.trade_history_builder = TradeHistoryBuilder(task, celery_task_id)
        self.metrics = MetricsCalculator(task, celery_task_id)
        self.equity_tracker = EquityTracker(task, celery_task_id)

    def load_state(self) -> ExecutionState[TStrategyState]:
        """Load execution state from task model.

        Returns:
            ExecutionState: Current execution state
        """
        from apps.trading.dataclasses import ExecutionMetrics

        # Refresh task from database
        self.task.refresh_from_db()

        # Check if we have existing state
        if self.task.result_data and isinstance(self.task.result_data, dict):
            state_dict = self.task.result_data.get("execution_state", {})
            if state_dict:
                # Load state from dict
                state = ExecutionState.from_dict(state_dict)
                # Deserialize strategy state
                strategy_state = self.strategy.deserialize_state(state.strategy_state)  # type: ignore[arg-type]
                state = state.copy_with(strategy_state=strategy_state)
                return state  # type: ignore[return-value]

        # Create initial state
        strategy_state_class = self.strategy.get_state_class()
        initial_strategy_state = strategy_state_class()

        return ExecutionState(
            strategy_state=initial_strategy_state,
            current_balance=self.initial_balance,
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics=ExecutionMetrics(),
        )

    def save_state(self, state: ExecutionState[TStrategyState]) -> None:
        """Save execution state to task model.

        Args:
            state: Execution state to save
        """
        # Serialize state
        state_dict = state.to_dict()

        # Update task result_data
        self.task.result_data = self.task.result_data or {}
        self.task.result_data["execution_state"] = state_dict
        self.task.result_data["equity_curve"] = state.equity_curve
        self.task.result_data["final_balance"] = str(state.current_balance)
        self.task.result_data["ticks_processed"] = state.ticks_processed
        self.task.result_data["metrics"] = state.metrics.to_dict()

        self.task.save(update_fields=["result_data", "updated_at"])

    def emit_events(self, events: list[StrategyEvent]) -> None:
        """Emit strategy events to database.

        Args:
            events: List of events to emit
        """
        if not events:
            return

        from apps.trading.models import TradingEvent

        # Create event records
        event_records = [
            TradingEvent(
                task_type="backtest",
                task_id=self.task.pk,
                event_type=event.event_type,
                severity="info",
                description=str(event.to_dict()),
                user=self.task.user,
                account=None,
                instrument=self.task.instrument,
                details=event.to_dict(),
            )
            for event in events
        ]

        # Bulk create
        TradingEvent.objects.bulk_create(event_records)


class TradingExecutor(TaskExecutor[TStrategyState]):
    """Executor for live trading tasks."""

    def __init__(
        self,
        *,
        task: TradingTasks,
        strategy: Strategy[TStrategyState],
        data_source: TickDataSource,
        controller: TaskController,
    ) -> None:
        """Initialize the trading executor.

        Args:
            task: Trading task instance
            strategy: Strategy instance to execute
            data_source: Tick data source
            controller: Task controller for lifecycle management
        """
        self.task = task

        # Create event context
        event_context = EventContext(
            user=task.user,
            account=task.oanda_account,
            instrument=task.instrument,
        )

        # Get initial balance from OANDA account
        initial_balance = task.oanda_account.balance

        super().__init__(
            strategy=strategy,
            data_source=data_source,
            controller=controller,
            event_context=event_context,
            initial_balance=initial_balance,
            instrument=task.instrument,
            pip_size=task._pip_size or Decimal("0.01"),
        )

    def load_state(self) -> ExecutionState[TStrategyState]:
        """Load execution state from task model.

        Returns:
            ExecutionState: Current execution state
        """
        from apps.trading.dataclasses import ExecutionMetrics

        # Refresh task from database
        self.task.refresh_from_db()

        # Check if we have existing state
        if self.task.result_data and isinstance(self.task.result_data, dict):
            state_dict = self.task.result_data.get("execution_state", {})
            if state_dict:
                # Load state from dict
                state = ExecutionState.from_dict(state_dict)
                # Deserialize strategy state
                strategy_state = self.strategy.deserialize_state(state.strategy_state)  # type: ignore[arg-type]
                state = state.copy_with(strategy_state=strategy_state)
                return state  # type: ignore[return-value]

        # Create initial state
        strategy_state_class = self.strategy.get_state_class()
        initial_strategy_state = strategy_state_class()

        return ExecutionState(
            strategy_state=initial_strategy_state,
            current_balance=self.initial_balance,
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics=ExecutionMetrics(),
        )

    def save_state(self, state: ExecutionState[TStrategyState]) -> None:
        """Save execution state to task model.

        Args:
            state: Execution state to save
        """
        # Serialize state
        state_dict = state.to_dict()

        # Update task result_data
        self.task.result_data = self.task.result_data or {}
        self.task.result_data["execution_state"] = state_dict
        self.task.result_data["current_balance"] = str(state.current_balance)
        self.task.result_data["ticks_processed"] = state.ticks_processed
        self.task.result_data["metrics"] = state.metrics.to_dict()

        self.task.save(update_fields=["result_data", "updated_at"])

    def emit_events(self, events: list[StrategyEvent]) -> None:
        """Emit strategy events to database.

        Args:
            events: List of events to emit
        """
        if not events:
            return

        from apps.trading.models import TradingEvent

        # Create event records
        event_records = [
            TradingEvent(
                task_type="trading",
                task_id=self.task.pk,
                event_type=event.event_type,
                severity="info",
                description=str(event.to_dict()),
                user=self.task.user,
                account=self.task.oanda_account,
                instrument=self.task.instrument,
                details=event.to_dict(),
            )
            for event in events
        ]

        # Bulk create
        TradingEvent.objects.bulk_create(event_records)
