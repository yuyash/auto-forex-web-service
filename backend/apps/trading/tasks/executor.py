"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from decimal import Decimal
from logging import Logger
from typing import TYPE_CHECKING, List

from apps.trading.dataclasses import (
    EventContext,
)
from apps.trading.enums import TaskType
from apps.trading.events import StrategyEvent
from apps.trading.models import TradingEvent
from apps.trading.models.state import ExecutionState
from apps.trading.services.controller import TaskController
from apps.trading.services.engine import TradingEngine
from apps.trading.services.handler import EventHandler
from apps.trading.services.order import OrderService, OrderServiceError
from apps.trading.tasks.source import TickDataSource

if TYPE_CHECKING:
    from apps.trading.models import BacktestTask, TradingTask

logger: Logger = logging.getLogger(name=__name__)


class TaskExecutor:
    """Abstract base class for task execution.

    This class provides the core execution loop for processing ticks through
    a trading engine, managing state, and handling lifecycle events.
    """

    def __init__(
        self,
        *,
        engine: TradingEngine,
        data_source: TickDataSource,
        controller: TaskController,
        event_context: EventContext,
        initial_balance: Decimal,
        instrument: str,
        pip_size: Decimal,
        task: BacktestTask | TradingTask,
        order_service: OrderService,
    ) -> None:
        """Initialize the executor.

        Args:
            engine: Trading engine instance
            data_source: Tick data source
            controller: Task controller for lifecycle management
            event_context: Context for event emission
            initial_balance: Initial account balance
            instrument: Trading instrument
            pip_size: Pip size for the instrument
            task: Task instance (BacktestTask or TradingTask)
            order_service: Service for executing orders
        """
        self.engine = engine
        self.data_source = data_source
        self.controller = controller
        self.event_context = event_context
        self.initial_balance = initial_balance
        self.instrument = instrument
        self.pip_size = pip_size
        self.task = task
        self.order_service = order_service
        self.event_handler = EventHandler(order_service, instrument)

    @property
    def task_type(self) -> TaskType:
        """Determine task type from task instance.

        Returns:
            TaskType enum value
        """
        from apps.trading.models import BacktestTask

        if isinstance(self.task, BacktestTask):
            return TaskType.BACKTEST
        return TaskType.TRADING

    @abstractmethod
    def handle_events(self, events: List[TradingEvent]) -> None:
        """Handle events from strategy."""
        pass

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
                task_type=self.task_type.value,
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id or "",
            )
            return state

        except ExecutionState.DoesNotExist:
            pass

        # Create initial state if not found
        state = ExecutionState.objects.create(
            task_type=self.task_type.value,
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

    def save_events(self, events: List[StrategyEvent]) -> List[TradingEvent]:
        """Save strategy events to database.

        Args:
            events: List of events to save
        """
        if not events:
            return []

        from apps.trading.models import TradingEvent

        # Create event records using from_event class method
        event_records: List[TradingEvent] = [
            TradingEvent.from_event(
                event=event,
                context=self.event_context,
                celery_task_id=self.task.celery_task_id,
            )
            for event in events
        ]

        # Bulk create
        TradingEvent.objects.bulk_create(event_records)
        return event_records

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
            result = self.engine.on_start(state=state)
            state = result.state
            self.save_events(result.events)
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
                    result = self.engine.on_tick(tick=tick, state=state)
                    state = result.state
                    events: List[TradingEvent] = self.save_events(result.events)

                    # Update metrics and trades from events
                    if events:
                        self.handle_events(events)
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
            result = self.engine.on_stop(state=state)
            state = result.state
            self.save_events(result.events)
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
        engine: TradingEngine,
        data_source: TickDataSource,
        controller: TaskController,
    ) -> None:
        """Initialize the backtest executor.

        Args:
            task: Backtest task instance
            engine: Trading engine instance
            data_source: Tick data source
            controller: Task controller for lifecycle management
        """
        # Create event context
        event_context = EventContext(
            user=task.user,
            account=None,  # No account for backtests
            instrument=task.instrument,
            task_id=task.pk,
            task_type=TaskType.BACKTEST,
        )

        # Create OrderService with dry_run=True for simulation
        from apps.market.models import OandaAccounts

        # Get user's first account for simulation (or create a dummy one)
        account = OandaAccounts.objects.filter(user=task.user, is_active=True).first()
        if not account:
            raise ValueError(f"No active OANDA account found for user {task.user}")

        order_service = OrderService(
            account=account,
            task=task,
            dry_run=True,  # Backtest mode - simulate orders
        )

        super().__init__(
            engine=engine,
            data_source=data_source,
            controller=controller,
            event_context=event_context,
            initial_balance=task.initial_balance,
            instrument=task.instrument,
            pip_size=task.pip_size or Decimal("0.01"),
            task=task,
            order_service=order_service,
        )

    def handle_events(self, events: List[TradingEvent]) -> None:
        """Handle events from strategy execution by executing orders.

        For backtests, this executes simulated orders through OrderService
        with dry_run=True.

        Args:
            events: List of TradingEvent instances that were saved
        """
        for trading_event in events:
            try:
                self.event_handler.handle_event(trading_event)
            except OrderServiceError as e:
                logger.error(
                    "Order execution failed for backtest event %s: %s",
                    trading_event.pk,
                    e,
                )
                # Continue processing other events in backtest mode

        logger.debug(
            "Processed %s events for backtest task %s (open positions: %s)",
            len(events),
            self.task.pk,
            len(self.event_handler.get_open_positions()),
        )


class TradingExecutor(TaskExecutor):
    """Executor for live trading tasks."""

    def __init__(
        self,
        *,
        task: TradingTask,
        engine: TradingEngine,
        data_source: TickDataSource,
        controller: TaskController,
    ) -> None:
        """Initialize the trading executor.

        Args:
            task: Trading task instance
            engine: Trading engine instance
            data_source: Tick data source
            controller: Task controller for lifecycle management
        """
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

        # Create OrderService with dry_run=False for live trading
        order_service = OrderService(
            account=task.oanda_account,
            task=task,
            dry_run=False,  # Live trading mode - execute real orders
        )

        super().__init__(
            engine=engine,
            data_source=data_source,
            controller=controller,
            event_context=event_context,
            initial_balance=initial_balance,
            instrument=task.instrument,
            pip_size=task.pip_size,
            task=task,
            order_service=order_service,
        )

    def handle_events(self, events: List[TradingEvent]) -> None:
        """Handle events from strategy execution by executing real orders.

        For live trading, this executes real orders through OrderService
        with dry_run=False.

        Args:
            events: List of TradingEvent instances that were saved
        """
        for trading_event in events:
            try:
                self.event_handler.handle_event(trading_event)
            except OrderServiceError as e:
                logger.error(
                    "Order execution failed for trading event %s: %s",
                    trading_event.pk,
                    e,
                    exc_info=True,
                )
                # For live trading, consider additional actions:
                # - Send alert/notification
                # - Pause strategy
                # - Log to monitoring system
                # For now, continue processing other events

        logger.debug(
            "Processed %s events for trading task %s (open positions: %s)",
            len(events),
            self.task.pk,
            len(self.event_handler.get_open_positions()),
        )
