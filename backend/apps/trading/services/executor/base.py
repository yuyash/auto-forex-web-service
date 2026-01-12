"""apps.trading.services.executor.base

Base executor class with common functionality for backtest and trading executors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import (
    EventContext,
    ExecutionState,
    TaskControl,
    Tick,
    ValidationResult,
)
from apps.trading.events import (
    StrategyEvent,
)
from apps.trading.models import TaskExecution
from apps.trading.services.base import Strategy
from apps.trading.services.controller import TaskController
from apps.trading.services.events import EventEmitter
from apps.trading.services.performance import PerformanceTracker
from apps.trading.services.source import TickDataSource
from apps.trading.services.state import StateManager

logger: Logger = getLogger(name=__name__)


class BaseExecutor(ABC):
    """Base executor class with common functionality.

    This abstract base class provides common functionality for both
    BacktestExecutor and TradingExecutor, including:
     - State management with persistence
     - Event emission and tracking
     - Performance metrics tracking
     - Task lifecycle control
     - Tick processing through strategy
    """

    def __init__(
        self,
        *,
        data_source: TickDataSource,
        strategy: Strategy,
        execution: TaskExecution,
        event_context: EventContext,
        initial_balance: Decimal,
        task_name: str,
    ) -> None:
        """Initialize the base executor.

        Args:
            data_source: TickDataSource instance that yields batches of ticks
            strategy: Strategy instance to execute (already initialized with pip_size)
            execution: TaskExecution model instance
            event_context: EventContext for event emission
            initial_balance: Initial account balance
            task_name: Name for task controller
        """
        self.data_source = data_source
        self.strategy = strategy
        self.execution = execution

        # Initialize services
        self.state_manager = StateManager(execution=execution)
        self.event_emitter = EventEmitter(context=event_context)
        self.performance_tracker = PerformanceTracker(
            execution=execution,
            initial_balance=initial_balance,
        )
        self.task_controller = TaskController(
            task_name=task_name,
            instance_key=str(execution.pk),
        )

        # Control flags
        self._should_stop = False

    def execute(self) -> None:
        """Execute the task.

        This is the main entry point for task execution. It:
        1. Starts the task controller
        2. Loads or initializes state
        3. Initializes the strategy
        4. Processes ticks through the strategy
        5. Handles stop requests
        6. Saves final state and metrics
        """
        try:
            # Start task controller
            self.task_controller.start()
            logger.info(f"Starting execution {self.execution.pk}")

            # Load or initialize state
            initial_balance = self._get_initial_balance()
            state = self.state_manager.load_or_initialize(
                initial_balance=initial_balance,
                initial_strategy_state={},
            )

            # Convert strategy_state from dict to proper StrategyState object
            if isinstance(state.strategy_state, dict):
                strategy_state_obj = self.strategy.initialize_strategy_state(state.strategy_state)
                state = state.copy_with(strategy_state=strategy_state_obj)

            # Validate state if resuming
            if state.ticks_processed > 0:
                validation_result: ValidationResult = self.state_manager.validate_state(state)
                if not validation_result.is_valid:
                    raise ValueError(
                        f"Invalid state for resumption: {validation_result.error_message}"
                    )
                logger.info(
                    f"Resuming from tick {state.ticks_processed} "
                    f"with balance {state.current_balance}"
                )

            # Initialize strategy
            result = self.strategy.on_start(state=state)
            state = result.state

            # Process initialization events
            for event in result.events:
                self._handle_strategy_event(event, state)

            # Process ticks
            self._process_ticks(state)

            # Stop strategy
            result = self.strategy.on_stop(state=state)
            state = result.state

            # Process stop events
            for event in result.events:
                self._handle_strategy_event(event, state)

            # Save final state
            self.state_manager.save_snapshot(state)

            # Save final metrics checkpoint
            self.performance_tracker.save_checkpoint()

            # Mark task as stopped
            self.task_controller.stop(
                status_message=f"Execution {self.execution.pk} completed successfully"
            )

            logger.info(f"Execution {self.execution.pk} completed")

        except Exception as e:
            logger.exception(f"Execution {self.execution.pk} failed: {e}")
            self.event_emitter.emit_error(e, error_context={"phase": "execution"})
            self.task_controller.stop(failed=True, status_message=str(e))
            raise

    def stop(self) -> None:
        """Stop the execution.

        Sets the stop flag, causing the executor to stop processing ticks.
        The current state is automatically persisted by periodic saves,
        allowing the execution to be resumed later.
        """
        self._should_stop = True
        logger.info(f"Execution {self.execution.pk} stopping")

    def _process_tick(self, tick: Tick, state: ExecutionState) -> ExecutionState:
        """Process a single tick through the strategy.

        Args:
            tick: Tick to process
            state: Current execution state

        Returns:
            ExecutionState: Updated execution state
        """
        result = self.strategy.on_tick(tick=tick, state=state)

        # Handle strategy events
        for event in result.events:
            self._handle_strategy_event(event, result.state)

        return result.state

    @abstractmethod
    def _get_initial_balance(self) -> Decimal:
        """Get the initial balance for this execution.

        Returns:
            Decimal: Initial account balance

        Note:
            Subclasses must implement this to provide the appropriate
            initial balance (from task config for backtests, from account for trading).
        """
        raise NotImplementedError

    def _process_ticks(self, state: ExecutionState) -> None:
        """Process ticks from the data source.

        Iterates through tick batches from the data source, processing each
        tick through the strategy. Handles periodic state saves and heartbeats.

        Args:
            state: Current execution state (modified in place)
        """
        ticks_since_last_save = 0
        ticks_since_last_heartbeat = 0
        save_interval = 100  # Save state every 100 ticks
        heartbeat_interval = 10  # Send heartbeat every 10 ticks

        try:
            for tick_batch in self.data_source:
                # Check for stop request
                control: TaskControl = self.task_controller.check_control()
                if control.should_stop:
                    logger.info("Stop requested, stopping execution")
                    self._should_stop = True
                    break

                if self._should_stop:
                    break

                # Process each tick in the batch
                for tick in tick_batch:
                    # Emit tick received event
                    self.event_emitter.emit_tick_received(tick)

                    # Process tick through strategy
                    state = self._process_tick(tick, state)

                    # Update performance tracker
                    self.performance_tracker.on_tick_processed()

                    # Periodic state save
                    ticks_since_last_save += 1
                    if ticks_since_last_save >= save_interval:
                        self.state_manager.save_snapshot(state)
                        self.performance_tracker.save_checkpoint()
                        ticks_since_last_save = 0

                    # Periodic heartbeat
                    ticks_since_last_heartbeat += 1
                    if ticks_since_last_heartbeat >= heartbeat_interval:
                        metrics = self.performance_tracker.get_metrics()
                        self.task_controller.heartbeat(
                            status_message=f"Processed {metrics['ticks_processed']} ticks",
                            meta_update=metrics,
                        )
                        ticks_since_last_heartbeat = 0

                    # Check for stop after each tick
                    if self._should_stop:
                        break

                if self._should_stop:
                    break

        except StopIteration:
            # Stream ended (normal for backtests, unexpected for live trading)
            logger.info("Data stream ended")
        except Exception as e:
            logger.exception(f"Error processing ticks: {e}")
            raise

    @abstractmethod
    def _handle_strategy_event(self, event: StrategyEvent, state: ExecutionState) -> None:
        """Handle a strategy event.

        Args:
            event: Strategy event object (typed subclass)
            state: Current execution state

        Note:
            Subclasses must implement this to handle strategy events
            appropriately (simulated trades for backtests, real trades for trading).
        """
        raise NotImplementedError
