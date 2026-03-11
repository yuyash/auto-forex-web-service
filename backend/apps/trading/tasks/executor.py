"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from logging import Logger, getLogger
from typing import List, cast

from django.utils import timezone as dj_timezone

from apps.trading.dataclasses import EventContext, EventExecutionResult, StrategyResult
from apps.trading.engine import TradingEngine
from apps.trading.enums import EventScope, EventType, TaskType
from apps.trading.events import StrategyEvent
from apps.trading.events.handler import EventHandler as _EventHandlerCompat
from apps.trading.models import BacktestTask, TradingEvent, TradingTask
from apps.trading.models.state import ExecutionState
from apps.trading.order import OrderService, OrderServiceError
from apps.trading.services.unrealized_pnl import update_unrealized_pnl
from apps.trading.tasks.source import TickDataSource
from apps.trading.tasks.state import StateManager

logger: Logger = getLogger(name=__name__)

# Backward-compatible export for tests patching this symbol.
EventHandler = _EventHandlerCompat


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


@dataclass(slots=True)
class ExecutionLoopState:
    """Mutable loop state for executor runtime."""

    state: ExecutionState
    batch_count: int = 0
    no_tick_batches: int = 0
    max_no_tick_batches: int = 60
    stopped_early: bool = False


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

        self.event_handler = self.engine.create_event_handler(
            order_service=order_service,
            instrument=self.instrument,
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
        for trading_event in events:
            if getattr(trading_event, "is_processed", False):
                continue

            if self.task_type == TaskType.TRADING and self._event_already_applied(
                trading_event=trading_event,
                state=state,
            ):
                self._mark_event_processed(trading_event)
                continue

            try:
                execution_result: EventExecutionResult = self.event_handler.handle_event(
                    trading_event
                )
                if execution_result.realized_pnl_delta != Decimal("0"):
                    state.current_balance = (
                        Decimal(str(state.current_balance)) + execution_result.realized_pnl_delta
                    )
                self.engine.apply_event_execution_result(
                    state=state,
                    execution_result=execution_result,
                )
                self._mark_event_processed(trading_event)

                # Trading resume requires state durability at event granularity.
                if self.task_type == TaskType.TRADING:
                    self.save_state(state)
            except OrderServiceError as e:
                logger.error(
                    "Order execution failed for trading event %s: %s",
                    trading_event.pk,
                    e,
                    exc_info=True,
                )
                self._mark_event_processing_error(trading_event, str(e))

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
        state, _ = self._load_state_with_metadata()
        return state

    def _load_state_with_metadata(self) -> tuple[ExecutionState, bool]:
        """Load state and indicate whether this execution is a resume."""
        self.task.refresh_from_db()

        try:
            state = ExecutionState.objects.get(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=self.task.execution_id,
            )
            return state, True
        except ExecutionState.DoesNotExist:
            pass

        from apps.trading.models import BacktestTask

        initial_timestamp = self.task.start_time if isinstance(self.task, BacktestTask) else None

        state = ExecutionState.objects.create(
            task_type=self.task_type.value,
            task_id=self.task.pk,
            execution_id=self.task.execution_id,
            strategy_state={},
            current_balance=self.initial_balance,
            ticks_processed=0,
            last_tick_timestamp=initial_timestamp,
        )
        return state, False

    def save_state(self, state: ExecutionState) -> None:
        """Save execution state to ExecutionState model.

        Args:
            state: Execution state to save
        """
        # Log what we're saving
        logger.debug(
            f"Saving state: task_id={state.task_id}, "
            f"ticks_processed={state.ticks_processed}, "
            f"last_tick_timestamp={state.last_tick_timestamp}, "
            f"current_balance={state.current_balance}"
        )

        # Save the model instance
        state.save()

    def _flush_metrics(self, state: ExecutionState) -> None:
        """Bulk-create buffered metrics and clear the buffer."""
        if not self._metric_buffer:
            return

        from apps.trading.models.metrics import Metrics

        buffer_size = len(self._metric_buffer)
        first_ts = self._metric_buffer[0].get("timestamp")
        last_ts = self._metric_buffer[-1].get("timestamp")

        objs = [
            Metrics(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=self.task.execution_id,
                timestamp=m["timestamp"],
                # Legacy Floor fields (populated from metrics dict for backward compat)
                margin_ratio=m.get("margin_ratio"),
                current_atr=m.get("current_atr"),
                baseline_atr=m.get("baseline_atr"),
                volatility_threshold=m.get("volatility_threshold"),
                # Generic metrics JSON (stores all strategy metrics)
                # Convert Decimal values to float for JSON serialization
                metrics={
                    k: float(v) if isinstance(v, Decimal) else v
                    for k, v in m.items()
                    if k != "timestamp" and v is not None
                },
            )
            for m in self._metric_buffer
        ]
        created = Metrics.objects.bulk_create(objs, ignore_conflicts=True)
        logger.debug(
            "Flushed metrics - task_id=%s, buffered=%d, created=%d, first_ts=%s, last_ts=%s",
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

        from apps.trading.models import StrategyEventRecord, TradingEvent

        trading_records: List[TradingEvent] = []
        strategy_records: list[StrategyEventRecord] = []

        for event in events:
            event_type = str(getattr(getattr(event, "event_type", None), "value", event.event_type))
            event_scope = EventType.scope_of(event_type)
            execution_event_type = EventType.execution_event_type_for(event_type)
            requires_execution = EventType.requires_execution(event_type)

            if requires_execution:
                if execution_event_type != event_type:
                    details = event.to_dict()
                    details["strategy_event_type"] = event_type
                    details["event_type"] = execution_event_type
                    trading_records.append(
                        TradingEvent(
                            event_type=execution_event_type,
                            severity="info",
                            description=str(details),
                            user=self.event_context.user,
                            account=self.event_context.account,
                            instrument=self.event_context.instrument,
                            task_type=self.event_context.task_type.value,
                            task_id=self.event_context.task_id,
                            execution_id=self.task.execution_id,
                            details=details,
                        )
                    )
                else:
                    trading_records.append(
                        TradingEvent.from_event(
                            event=event,
                            context=self.event_context,
                            execution_id=self.task.execution_id,
                        )
                    )

            if event_scope == EventScope.TASK.value and not requires_execution:
                trading_records.append(
                    TradingEvent.from_event(
                        event=event,
                        context=self.event_context,
                        execution_id=self.task.execution_id,
                    )
                )
            elif event_scope == EventScope.STRATEGY.value:
                strategy_records.append(
                    StrategyEventRecord.from_event(
                        event=event,
                        context=self.event_context,
                        execution_id=self.task.execution_id,
                    )
                )

        if trading_records:
            TradingEvent.objects.bulk_create(trading_records)
        if strategy_records:
            StrategyEventRecord.objects.bulk_create(strategy_records)

        return trading_records

    def execute(self) -> None:
        """Execute the task."""
        try:
            loop = ExecutionLoopState(state=self._start_execution())
            self._run_tick_loop(loop)
            self._finalize_execution(loop)
        except Exception as e:
            self._handle_execution_failure(e)
            raise
        finally:
            self._cleanup_execution()

    def prepare_state_for_execution(
        self,
        *,
        state: ExecutionState,
        resumed: bool,
    ) -> ExecutionState:
        """Hook for executor-specific state preparation before start/resume."""
        _ = resumed
        return state

    def _run_start_hook(
        self,
        *,
        state: ExecutionState,
        resumed: bool,
    ) -> StrategyResult:
        if resumed:
            return self.engine.on_resume(state=state)
        return self.engine.on_start(state=state)

    def _start_execution(self) -> ExecutionState:
        """Initialize coordinator/state and run strategy start hook."""
        logger.info("Starting task execution")
        self.state_manager.start(
            celery_task_id=str(self.task.execution_id) if self.task.execution_id else None,
            meta={"execution_id": str(self.task.execution_id) if self.task.execution_id else None},
        )

        state, resumed = self._load_state_with_metadata()
        state = self.prepare_state_for_execution(state=state, resumed=resumed)
        logger.info(
            "State loaded: balance=%s, ticks_processed=%d, resumed=%s",
            state.current_balance,
            state.ticks_processed,
            resumed,
        )

        if resumed and self.task_type == TaskType.TRADING:
            self._replay_unprocessed_events(state)

        logger.info("Starting trading engine lifecycle hook...")
        result = self._run_start_hook(state=state, resumed=resumed)
        state = result.state
        self.save_events(result.events)
        self.save_state(state)
        logger.info("Engine started, events_count=%d", len(result.events))
        return state

    def _run_tick_loop(self, loop: ExecutionLoopState) -> None:
        """Run batch/tick processing loop."""
        logger.info("Starting tick processing loop")

        for tick_batch in self.data_source:
            if self._should_stop_before_batch(loop):
                break

            if not tick_batch:
                if self._handle_empty_batch(loop):
                    break
                continue

            loop.no_tick_batches = 0
            self._process_tick_batch(loop, tick_batch)
            loop.batch_count += 1
            self._persist_batch_progress(loop)

            if loop.stopped_early:
                break

        logger.info(
            "Exited tick processing loop - task_id=%s, stopped_early=%s, ticks_processed=%d",
            self.task.pk,
            loop.stopped_early,
            loop.state.ticks_processed,
        )

    def _should_stop_before_batch(self, loop: ExecutionLoopState) -> bool:
        """Check external stop signal before processing a batch."""
        control = self.state_manager.check_control()
        if not control.should_stop:
            return False

        logger.info("Stop signal received - ticks_processed=%d", loop.state.ticks_processed)
        loop.stopped_early = True
        return True

    def _handle_empty_batch(self, loop: ExecutionLoopState) -> bool:
        """Handle empty tick batch; return True when loop should terminate."""
        if self.task_type == TaskType.TRADING and is_forex_market_closed():
            if loop.no_tick_batches == 0:
                logger.info("Market is closed, tolerating empty batches")
            loop.no_tick_batches = 0
            return False

        loop.no_tick_batches += 1
        if loop.no_tick_batches < loop.max_no_tick_batches:
            return False

        logger.warning(
            "No ticks received for %d consecutive batches. Data source may have ended without EOF signal.",
            loop.no_tick_batches,
        )
        return True

    def _process_tick_batch(self, loop: ExecutionLoopState, tick_batch: list) -> None:
        """Process one non-empty batch."""
        for tick_idx, tick in enumerate(tick_batch):
            if tick_idx % 100 == 0 and self._should_stop_during_batch(loop, tick_idx):
                break
            if self._process_single_tick(loop, tick):
                break

    def _should_stop_during_batch(self, loop: ExecutionLoopState, tick_idx: int) -> bool:
        """Check stop signal during long batch processing."""
        control = self.state_manager.check_control()
        if not control.should_stop:
            return False

        logger.info(
            "Stop signal received during batch processing - task_id=%s, task_type=%s, ticks_processed=%d, tick_idx=%d",
            self.task.pk,
            self.task_type.value,
            loop.state.ticks_processed,
            tick_idx,
        )
        loop.stopped_early = True
        return True

    def _process_single_tick(self, loop: ExecutionLoopState, tick) -> bool:
        """Process one tick; return True when execution should stop."""
        result: StrategyResult = self.engine.on_tick(tick=tick, state=loop.state)
        loop.state = result.state
        events: List[TradingEvent] = self.save_events(result.events)

        if self.task_type == TaskType.TRADING and events:
            # Persist exact strategy state at event emission time.
            self.save_state(loop.state)

        if events:
            self.handle_events(loop.state, events)

        if result.should_stop:
            logger.warning(
                "Strategy requested stop: %s — ticks_processed=%d",
                result.stop_reason,
                loop.state.ticks_processed,
            )
            loop.stopped_early = True
            return True

        loop.state.ticks_processed += 1
        loop.state.last_tick_timestamp = tick.timestamp
        loop.state.last_tick_price = tick.mid
        loop.state.last_tick_bid = tick.bid
        loop.state.last_tick_ask = tick.ask
        self._buffer_tick_metrics(loop.state, tick)
        return False

    def _replay_unprocessed_events(self, state: ExecutionState) -> None:
        """Replay pending events that were persisted before a crash."""
        pending_events = list(
            TradingEvent.objects.filter(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=self.task.execution_id,
                is_processed=False,
            ).order_by("created_at", "id")
        )

        if not pending_events:
            return

        logger.warning(
            "Replaying %d unprocessed event(s) before resume - task_id=%s",
            len(pending_events),
            self.task.pk,
        )
        self.handle_events(state, pending_events)
        self.save_state(state)

    def _event_already_applied(
        self,
        *,
        trading_event: TradingEvent,
        state: ExecutionState,
    ) -> bool:
        """Best-effort idempotency guard for resumed event replay."""
        from apps.trading.events import (
            ClosePositionEvent,
            MarginProtectionEvent,
            OpenPositionEvent,
            StrategyEvent,
            VolatilityHedgeNeutralizeEvent,
            VolatilityLockEvent,
        )
        from apps.trading.models import Position

        strategy_event = StrategyEvent.from_dict(trading_event.details)
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}

        if isinstance(strategy_event, OpenPositionEvent):
            entry_id = strategy_event.entry_id
            if entry_id is None:
                return False
            open_entries = strategy_state.get("open_entries")
            if not isinstance(open_entries, list):
                return False
            for entry in open_entries:
                if not isinstance(entry, dict):
                    continue
                try:
                    current_entry_id = int(entry.get("entry_id", -1))
                except (TypeError, ValueError):
                    continue
                if current_entry_id != int(entry_id):
                    continue
                position_id = str(entry.get("position_id") or "").strip()
                if not position_id:
                    return False
                exists = Position.objects.filter(
                    id=position_id,
                    task_type=self.task_type.value,
                    task_id=self.task.pk,
                    execution_id=self.task.execution_id,
                    is_open=True,
                ).exists()
                return bool(exists)
            return False

        if isinstance(strategy_event, ClosePositionEvent):
            position_id = str(strategy_event.position_id or "").strip()
            if not position_id:
                return False
            return not Position.objects.filter(
                id=position_id,
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=self.task.execution_id,
                is_open=True,
            ).exists()

        if isinstance(strategy_event, (VolatilityLockEvent, MarginProtectionEvent)):
            return not Position.objects.filter(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=self.task.execution_id,
                instrument=self.instrument,
                is_open=True,
            ).exists()

        if isinstance(strategy_event, VolatilityHedgeNeutralizeEvent):
            return False

        return False

    @staticmethod
    def _mark_event_processed(trading_event: TradingEvent) -> None:
        update_data = {
            "is_processed": True,
            "processed_at": dj_timezone.now(),
            "processing_error": "",
        }
        type(trading_event).objects.filter(pk=trading_event.pk).update(**update_data)
        trading_event.is_processed = True
        trading_event.processed_at = update_data["processed_at"]
        trading_event.processing_error = ""

    @staticmethod
    def _mark_event_processing_error(trading_event: TradingEvent, message: str) -> None:
        type(trading_event).objects.filter(pk=trading_event.pk).update(
            processing_error=str(message)[:4000]
        )
        trading_event.processing_error = str(message)[:4000]

    def _buffer_tick_metrics(self, state: ExecutionState, tick) -> None:
        """Buffer strategy metrics from current state for time-series persistence."""
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
            return

        logger.debug(
            "No metrics in strategy_state at tick %s (ticks_processed=%d)",
            tick.timestamp,
            state.ticks_processed,
        )

    def _persist_batch_progress(self, loop: ExecutionLoopState) -> None:
        """Persist state/metrics and emit periodic telemetry."""
        logger.debug(
            "Saving state after batch - task_id=%s, batch_count=%d, ticks_processed=%d",
            self.task.pk,
            loop.batch_count,
            loop.state.ticks_processed,
        )
        self.save_state(loop.state)
        self._flush_metrics(loop.state)
        self._update_unrealized_pnl(loop.state)
        self._emit_batch_telemetry(loop)

    def _update_unrealized_pnl(self, state: ExecutionState) -> None:
        """Recalculate unrealized pnl for open positions from latest tick."""
        if state.last_tick_price is None:
            return

        update_unrealized_pnl(
            task_type=self.task_type.value,
            task_id=str(self.task.pk),
            current_price=Decimal(str(state.last_tick_price)),
            execution_id=self.task.execution_id,
        )

    def _emit_batch_telemetry(self, loop: ExecutionLoopState) -> None:
        """Emit periodic progress logs and heartbeat updates."""
        if loop.batch_count % 50 == 0:
            logger.debug(
                "Metrics progress - task_id=%s, batch=%d, ticks_processed=%d, metric_buffer_size=%d, last_tick_ts=%s",
                self.task.pk,
                loop.batch_count,
                loop.state.ticks_processed,
                len(self._metric_buffer),
                loop.state.last_tick_timestamp,
            )

        if loop.batch_count % 10 == 0:
            logger.debug(
                "Sending heartbeat - task_id=%s, batch_count=%d, ticks_processed=%d",
                self.task.pk,
                loop.batch_count,
                loop.state.ticks_processed,
            )
            self.state_manager.heartbeat(
                status_message=f"Processed {loop.state.ticks_processed} ticks"
            )

    def _finalize_execution(self, loop: ExecutionLoopState) -> None:
        """Run stop hook and persist final stop state."""
        logger.info("Calling engine.on_stop")
        result = self.engine.on_stop(state=loop.state)
        loop.state = result.state
        self.save_events(result.events)
        self.save_state(loop.state)
        logger.info("Engine stopped, events_count=%d", len(result.events))

        if loop.stopped_early:
            logger.info(
                "Execution stopped by user - ticks_processed=%d, final_balance=%s",
                loop.state.ticks_processed,
                loop.state.current_balance,
            )
            self.state_manager.stop(status_message="Execution stopped by user")
            return

        logger.info(
            "Execution completed successfully - ticks_processed=%d, final_balance=%s",
            loop.state.ticks_processed,
            loop.state.current_balance,
        )
        self.state_manager.stop(status_message="Execution completed successfully", completed=True)

    def _handle_execution_failure(self, error: Exception) -> None:
        """Record failed execution outcome."""
        logger.error("Execution failed: %s", error, exc_info=True)
        self.state_manager.stop(status_message=f"Execution failed: {error}", failed=True)

    def _cleanup_execution(self) -> None:
        """Release runtime resources."""
        try:
            self.data_source.close()
        except Exception as e:
            logger.warning("Failed to close data source: %s", e)
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
            execution_id=task.execution_id,
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
            instance_key=f"{task.pk}:{task.execution_id}",
            task_id=str(task.pk),
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

    def prepare_state_for_execution(
        self,
        *,
        state: ExecutionState,
        resumed: bool,
    ) -> ExecutionState:
        """Reconcile broker/local state before resuming a recovered run."""
        if not resumed:
            return state

        from apps.trading.services.reconciliation import TradingResumeReconciler

        trading_task = cast(TradingTask, self.task)
        reconciler = TradingResumeReconciler(
            task=trading_task,
            state=state,
        )
        report = reconciler.reconcile()
        logger.info(
            "Trading resume reconciliation complete - task_id=%s, execution_id=%s, "
            "account=%s, closed_local=%d, created_local=%d, updated_local=%d, "
            "removed_entries=%d, synthesized_entries=%d, relinked_entries=%d",
            self.task.pk,
            self.task.execution_id,
            report.updated_account_snapshot,
            report.closed_local_positions,
            report.created_local_positions,
            report.updated_local_positions,
            report.removed_open_entries,
            report.synthesized_open_entries,
            report.relinked_open_entries,
        )
        return state

    def __init__(
        self,
        *,
        task: TradingTask,
        engine: TradingEngine,
        data_source: TickDataSource,
        dry_run: bool = False,
    ) -> None:
        """Initialize the trading executor.

        Args:
            task: Trading task instance
            engine: Trading engine instance
            data_source: Tick data source
            dry_run: If True, simulate orders without placing real orders on OANDA
        """
        # Create event context
        event_context = EventContext(
            user=task.user,
            account=task.oanda_account,
            instrument=task.instrument,
            task_id=task.pk,
            execution_id=task.execution_id,
            task_type=TaskType.TRADING,
        )

        # Create OrderService (respect dry_run flag)
        order_service = OrderService(
            account=task.oanda_account,
            task=task,
            dry_run=dry_run,
        )

        # Create state manager
        state_manager = StateManager(
            task_name="trading.tasks.run_trading_task",
            instance_key=f"{task.pk}:{task.execution_id}",
            task_id=str(task.pk),
        )

        super().__init__(
            task=task,
            engine=engine,
            data_source=data_source,
            event_context=event_context,
            order_service=order_service,
            state_manager=state_manager,
        )
