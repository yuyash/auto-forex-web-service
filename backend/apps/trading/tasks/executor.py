"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import List

from apps.trading.dataclasses import EventContext, StrategyResult
from apps.trading.engine import TradingEngine
from apps.trading.enums import TaskType
from apps.trading.events import StrategyEvent
from apps.trading.events.handler import EventHandler
from apps.trading.models import BacktestTask, TradingEvent, TradingTask
from apps.trading.models.state import ExecutionState
from apps.trading.order import OrderService, OrderServiceError
from apps.trading.tasks.source import TickDataSource
from apps.trading.tasks.state import StateManager

logger: Logger = getLogger(name=__name__)


def is_forex_market_closed() -> bool:
    """Check if the forex market is currently closed (weekend).

    Forex market closes Friday 21:00 UTC and reopens Sunday 21:00 UTC.
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour
    return (
        (weekday == 4 and hour >= 21)  # Friday after 21:00
        or weekday == 5  # Saturday
        or (weekday == 6 and hour < 21)  # Sunday before 21:00
    )


class TaskExecutor:
    """Abstract base class for task execution.

    This class provides the core execution loop for processing ticks through
    a trading engine, managing state, handling lifecycle events, and coordinating
    task execution via Redis.
    """

    def __init__(
        self,
        *,
        task: BacktestTask | TradingTask,
        engine: TradingEngine,
        data_source: TickDataSource,
        event_context: EventContext,
        order_service: OrderService,
        state_manager: StateManager,
    ) -> None:
        """Initialize the executor.

        Args:
            task: Task instance (BacktestTask or TradingTask)
            engine: Trading engine instance
            data_source: Tick data source
            event_context: Context for event emission
            order_service: Service for executing orders
            state_manager: State manager for Redis coordination
        """
        self.task: TradingTask | BacktestTask = task
        self.engine = engine
        self.data_source = data_source
        self.event_context = event_context
        self.order_service = order_service
        self.state_manager = state_manager

        # Extract properties from task
        self.instrument = task.instrument
        self.pip_size = task.pip_size
        self.initial_balance = self._get_initial_balance()

        self.event_handler = EventHandler(
            order_service, self.instrument, trading_mode=getattr(task, "trading_mode", "hedging")
        )

        self._metric_buffer: list[dict] = []

        logger.info(
            "TaskExecutor initialized: instrument=%s, pip_size=%s, initial_balance=%s",
            self.instrument,
            self.pip_size,
            self.initial_balance,
        )

    def _get_initial_balance(self) -> Decimal:
        """Get initial balance from task.

        Returns:
            Initial balance for the task
        """
        from apps.trading.models import BacktestTask

        if isinstance(self.task, BacktestTask):
            return self.task.initial_balance
        else:
            # For trading tasks, get balance from OANDA account
            return self.task.oanda_account.balance

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

    def handle_events(self, state: ExecutionState, events: List[TradingEvent]) -> None:
        """Handle events from strategy execution.

        Args:
            events: List of TradingEvent instances that were saved
        """
        realized_delta_total = Decimal("0")
        for trading_event in events:
            try:
                realized_delta_total += self.event_handler.handle_event(trading_event)
            except OrderServiceError as e:
                logger.error(
                    "Order execution failed for trading event %s: %s",
                    trading_event.pk,
                    e,
                    exc_info=True,
                )

        if realized_delta_total != Decimal("0"):
            state.current_balance = Decimal(str(state.current_balance)) + realized_delta_total
            logger.info(
                "Applied realized pnl to balance: delta=%s, new_balance=%s",
                realized_delta_total,
                state.current_balance,
            )

        logger.debug(
            "Processed %s events for trading task %s (open positions: %s)",
            len(events),
            self.task.pk,
            len(self.event_handler.get_open_positions()),
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
                task_type=self.task_type.value,
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id or "",
            )
            return state

        except ExecutionState.DoesNotExist:
            pass

        # Create initial state if not found
        # For BacktestTask, use start_time; for TradingTask, use current time
        from apps.trading.models import BacktestTask

        initial_timestamp = (
            self.task.start_time
            if isinstance(self.task, BacktestTask) and hasattr(self.task, "start_time")
            else None
        )

        state = ExecutionState.objects.create(
            task_type=self.task_type.value,
            task_id=self.task.pk,
            celery_task_id=self.task.celery_task_id or "",
            strategy_state={},
            current_balance=self.initial_balance,
            ticks_processed=0,
            last_tick_timestamp=initial_timestamp,  # Initialize with start_time for progress calculation
        )
        return state

    def save_state(self, state: ExecutionState) -> None:
        """Save execution state to ExecutionState model.

        Args:
            state: Execution state to save
        """
        import logging

        logger = logging.getLogger(__name__)

        # Log what we're saving
        logger.debug(
            f"Saving state: task_id={state.task_id}, "
            f"ticks_processed={state.ticks_processed}, "
            f"last_tick_timestamp={state.last_tick_timestamp}, "
            f"current_balance={state.current_balance}"
        )

        # Save the model instance
        state.save()

        # Verify it was saved
        state.refresh_from_db()
        logger.debug(f"State saved and verified: ticks_processed={state.ticks_processed}")

    def _flush_metric_snapshots(self, state: ExecutionState) -> None:
        """Bulk-create buffered metric snapshots and clear the buffer."""
        if not self._metric_buffer:
            return

        from apps.trading.models.metric_snapshots import MetricSnapshot

        buffer_size = len(self._metric_buffer)
        first_ts = self._metric_buffer[0].get("timestamp")
        last_ts = self._metric_buffer[-1].get("timestamp")

        objs = [
            MetricSnapshot(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id,
                timestamp=m["timestamp"],
                margin_ratio=m.get("margin_ratio"),
                current_atr=m.get("current_atr"),
                baseline_atr=m.get("baseline_atr"),
                volatility_threshold=m.get("volatility_threshold"),
            )
            for m in self._metric_buffer
        ]
        created = MetricSnapshot.objects.bulk_create(objs, ignore_conflicts=True)
        logger.debug(
            "Flushed metric snapshots - task_id=%s, buffered=%d, created=%d, "
            "first_ts=%s, last_ts=%s",
            self.task.pk,
            buffer_size,
            len(created),
            first_ts,
            last_ts,
        )
        self._metric_buffer.clear()

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
        """Execute the task."""
        try:
            # Start coordination
            logger.info("Starting task execution")
            self.state_manager.start()

            # Load state
            state = self.load_state()
            logger.info(
                "State loaded: balance=%s, ticks_processed=%d",
                state.current_balance,
                state.ticks_processed,
            )

            # Call on_start
            logger.info("Starting trading engine...")
            result = self.engine.on_start(state=state)
            state = result.state
            self.save_events(result.events)
            self.save_state(state)
            logger.info("Engine started, events_count=%d", len(result.events))

            # Process ticks
            batch_count = 0
            no_tick_batches = 0
            max_no_tick_batches = 60  # 60 empty batches = ~60 seconds without ticks
            stopped_early = False  # Track if we stopped before completion

            logger.info("Starting tick processing loop")

            for tick_batch in self.data_source:
                # Check for stop signal
                control = self.state_manager.check_control()
                if control.should_stop:
                    logger.info(
                        "Stop signal received - ticks_processed=%d",
                        state.ticks_processed,
                    )
                    stopped_early = True
                    break

                # Check if we received an empty batch
                if not tick_batch:
                    # During market close, empty batches are expected for live
                    # trading — don't count them toward the timeout.
                    if self.task_type == TaskType.TRADING and is_forex_market_closed():
                        if no_tick_batches == 0:
                            logger.info("Market is closed, tolerating empty batches")
                        no_tick_batches = 0
                    else:
                        no_tick_batches += 1
                        if no_tick_batches >= max_no_tick_batches:
                            logger.warning(
                                f"No ticks received for {no_tick_batches} consecutive batches. "
                                f"Data source may have ended without EOF signal."
                            )
                            break
                    continue

                # Reset no-tick counter when we receive ticks
                no_tick_batches = 0

                # Break out of batch loop if stopped during tick processing
                if stopped_early:
                    break

                # Process each tick in batch
                for tick_idx, tick in enumerate(tick_batch):
                    # Check for stop signal every 100 ticks within a batch
                    if tick_idx % 100 == 0:
                        control = self.state_manager.check_control()
                        if control.should_stop:
                            logger.info(
                                f"Stop signal received during batch processing - "
                                f"task_id={self.task.pk}, task_type={self.task_type.value}, "
                                f"ticks_processed={state.ticks_processed}, tick_idx={tick_idx}"
                            )
                            stopped_early = True
                            break

                    result: StrategyResult = self.engine.on_tick(tick=tick, state=state)
                    state: ExecutionState = result.state
                    events: List[TradingEvent] = self.save_events(result.events)

                    # Update metrics and trades from events
                    if events:
                        self.handle_events(state, events)

                    # Strategy requested task stop (e.g. margin blow-out)
                    if result.should_stop:
                        logger.warning(
                            "Strategy requested stop: %s — ticks_processed=%d",
                            result.stop_reason,
                            state.ticks_processed,
                        )
                        stopped_early = True
                        break

                    # Update tick count and timestamp
                    state.ticks_processed += 1
                    state.last_tick_timestamp = tick.timestamp
                    state.last_tick_price = tick.mid

                    # Buffer metric snapshot from strategy state
                    metrics = (state.strategy_state or {}).get("metrics", {})
                    if metrics:
                        self._metric_buffer.append(
                            {
                                "timestamp": tick.timestamp,
                                "margin_ratio": metrics.get("margin_ratio"),
                                "current_atr": metrics.get("current_atr"),
                                "baseline_atr": metrics.get("baseline_atr"),
                                "volatility_threshold": metrics.get("volatility_threshold"),
                            }
                        )
                    else:
                        logger.debug(
                            "No metrics in strategy_state at tick %s (ticks_processed=%d)",
                            tick.timestamp,
                            state.ticks_processed,
                        )

                # Increment batch counter
                batch_count += 1

                # Save state after every batch for real-time progress updates
                logger.debug(
                    f"Saving state after batch - task_id={self.task.pk}, "
                    f"batch_count={batch_count}, ticks_processed={state.ticks_processed}"
                )
                self.save_state(state)
                self._flush_metric_snapshots(state)

                if batch_count % 50 == 0:
                    logger.info(
                        "Metric snapshot progress - task_id=%s, batch=%d, "
                        "ticks_processed=%d, metric_buffer_size=%d, "
                        "last_tick_ts=%s",
                        self.task.pk,
                        batch_count,
                        state.ticks_processed,
                        len(self._metric_buffer),
                        state.last_tick_timestamp,
                    )

                # Send heartbeat every 10 batches
                if batch_count % 10 == 0:
                    logger.debug(
                        f"Sending heartbeat - task_id={self.task.pk}, "
                        f"batch_count={batch_count}, ticks_processed={state.ticks_processed}"
                    )
                    self.state_manager.heartbeat(
                        status_message=f"Processed {state.ticks_processed} ticks"
                    )

            logger.info(
                f"Exited tick processing loop - task_id={self.task.pk}, "
                f"stopped_early={stopped_early}, ticks_processed={state.ticks_processed}"
            )

            # Call on_stop
            logger.info("Calling engine.on_stop")
            result = self.engine.on_stop(state=state)
            state = result.state
            self.save_events(result.events)
            self.save_state(state)
            logger.info("Engine stopped, events_count=%d", len(result.events))

            # Mark as stopped with appropriate status
            if stopped_early:
                logger.info(
                    "Execution stopped by user - ticks_processed=%d, final_balance=%s",
                    state.ticks_processed,
                    state.current_balance,
                )
                self.state_manager.stop(status_message="Execution stopped by user")
            else:
                logger.info(
                    "Execution completed successfully - ticks_processed=%d, final_balance=%s",
                    state.ticks_processed,
                    state.current_balance,
                )
                self.state_manager.stop(
                    status_message="Execution completed successfully", completed=True
                )
        except Exception as e:
            logger.error("Execution failed: %s", e, exc_info=True)
            self.state_manager.stop(status_message=f"Execution failed: {e}", failed=True)
            raise
        finally:
            # Clean up data source
            try:
                self.data_source.close()
            except Exception as e:
                logger.warning(f"Failed to close data source: {e}")
            # Clean up state manager
            self.state_manager.cleanup()


class BacktestExecutor(TaskExecutor):
    """Executor for backtest tasks."""

    def __init__(
        self,
        *,
        task: BacktestTask,
        engine: TradingEngine,
        data_source: TickDataSource,
    ) -> None:
        """Initialize the backtest executor.

        Args:
            task: Backtest task instance
            engine: Trading engine instance
            data_source: Tick data source
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
        # No OANDA account needed for backtests - they run in pure simulation mode
        order_service = OrderService(
            account=None,  # Backtests don't need a real OANDA account
            task=task,
            dry_run=True,  # Backtest mode - simulate orders
        )

        # Create state manager
        state_manager = StateManager(
            task_name="trading.tasks.run_backtest_task",
            instance_key=str(task.pk),
            task_id=int(task.pk),
        )

        super().__init__(
            task=task,
            engine=engine,
            data_source=data_source,
            event_context=event_context,
            order_service=order_service,
            state_manager=state_manager,
        )


class TradingExecutor(TaskExecutor):
    """Executor for live trading tasks."""

    def __init__(
        self,
        *,
        task: TradingTask,
        engine: TradingEngine,
        data_source: TickDataSource,
    ) -> None:
        """Initialize the trading executor.

        Args:
            task: Trading task instance
            engine: Trading engine instance
            data_source: Tick data source
        """
        # Create event context
        event_context = EventContext(
            user=task.user,
            account=task.oanda_account,
            instrument=task.instrument,
            task_id=task.pk,
            task_type=TaskType.TRADING,
        )

        # Create OrderService with dry_run=False for live trading
        order_service = OrderService(
            account=task.oanda_account,
            task=task,
            dry_run=False,  # Live trading mode - execute real orders
        )

        # Create state manager
        state_manager = StateManager(
            task_name="trading.tasks.run_trading_task",
            instance_key=str(task.pk),
            task_id=int(task.pk),
        )

        super().__init__(
            task=task,
            engine=engine,
            data_source=data_source,
            event_context=event_context,
            order_service=order_service,
            state_manager=state_manager,
        )
