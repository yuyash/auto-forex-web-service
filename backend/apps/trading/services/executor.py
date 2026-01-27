"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from logging import Logger
from typing import TYPE_CHECKING

from apps.trading.dataclasses import (
    EventContext,
)
from apps.trading.enums import TaskType
from apps.trading.events import StrategyEvent
from apps.trading.models.state import ExecutionState
from apps.trading.services.controller import TaskController
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy

if TYPE_CHECKING:
    from apps.trading.models import BacktestTask, TradingTask

logger: Logger = logging.getLogger(name=__name__)


class TaskExecutor(ABC):
    """Abstract base class for task execution.

    This class provides the core execution loop for processing ticks through
    a strategy, managing state, and handling lifecycle events.
    """

    def __init__(
        self,
        *,
        strategy: Strategy,
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
    def load_state(self) -> ExecutionState:
        """Load execution state from storage.

        Returns:
            ExecutionState: Current execution state
        """
        ...

    @abstractmethod
    def save_state(self, state: ExecutionState) -> None:
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
                    state.ticks_processed += 1
                    if tick.timestamp:
                        state.last_tick_timestamp = tick.timestamp

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


class BacktestExecutor(TaskExecutor):
    """Executor for backtest tasks."""

    def __init__(
        self,
        *,
        task: BacktestTask,
        strategy: Strategy,
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
            task_id=task.pk,
            task_type=TaskType.BACKTEST,
        )

        super().__init__(
            strategy=strategy,
            data_source=data_source,
            controller=controller,
            event_context=event_context,
            initial_balance=task.initial_balance,
            instrument=task.instrument,
            pip_size=task.pip_size or Decimal("0.01"),
        )

    def load_state(self) -> ExecutionState:
        """Load execution state from ExecutionState model.

        Returns:
            ExecutionState: Current execution state
        """
        # Refresh task from database
        self.task.refresh_from_db()

        # Try to load from ExecutionState model
        try:
            state = ExecutionState.objects.get(
                task_type="backtest",
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id or "",
            )
            return state

        except ExecutionState.DoesNotExist:
            pass

        # Create initial state if not found

        state = ExecutionState.objects.create(
            task_type="backtest",
            task_id=self.task.pk,
            celery_task_id=self.task.celery_task_id or "",
            strategy_state={},
            current_balance=self.initial_balance,
            ticks_processed=0,
            last_tick_timestamp=None,
        )
        return state

    def save_state(self, state: ExecutionState) -> None:
        """Save execution state to ExecutionState model.

        Args:
            state: Execution state to save
        """
        # Save the model instance
        state.save()

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
                celery_task_id=self.task.celery_task_id,
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


class TradingExecutor(TaskExecutor):
    """Executor for live trading tasks."""

    def __init__(
        self,
        *,
        task: TradingTask,
        strategy: Strategy,
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
            task_id=task.pk,
            task_type=TaskType.TRADING,
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
            pip_size=task.pip_size or Decimal("0.01"),
        )

    def load_state(self) -> ExecutionState:
        """Load execution state from ExecutionState model.

        Returns:
            ExecutionState: Current execution state
        """
        # Refresh task from database
        self.task.refresh_from_db()

        # Try to load from ExecutionState model
        try:
            state = ExecutionState.objects.get(
                task_type="trading",
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id or "",
            )
            return state

        except ExecutionState.DoesNotExist:
            pass

        # Create initial state if not found
        state = ExecutionState.objects.create(
            task_type="trading",
            task_id=self.task.pk,
            celery_task_id=self.task.celery_task_id or "",
            strategy_state={},
            current_balance=self.initial_balance,
            ticks_processed=0,
            last_tick_timestamp=None,
        )
        return state

    def save_state(self, state: ExecutionState) -> None:
        """Save execution state to ExecutionState model.

        Args:
            state: Execution state to save
        """
        # Save the model instance
        state.save()

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
                celery_task_id=self.task.celery_task_id,
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
