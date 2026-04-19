"""Task execution engine for backtests and live trading.

This module provides the core execution engine that processes ticks through
strategies, manages state, and handles lifecycle events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from decimal import Decimal
from logging import Logger, getLogger
from typing import List, cast

from django.utils import timezone as dj_timezone

from apps.trading.dataclasses import EventContext, EventExecutionResult, StrategyResult
from apps.trading.engine import TradingEngine
from apps.trading.enums import EventScope, EventType, TaskStatus, TaskType
from apps.trading.events import StrategyEvent
from apps.trading.events.handler import EventHandler as _EventHandlerCompat
from apps.trading.events.handler import CycleResolutionError  # noqa: F401 — used in handle_events
from apps.trading.models import BacktestTask, TradingEvent, TradingTask
from apps.trading.models.state import ExecutionState
from apps.trading.order import OrderService, OrderServiceError
from apps.trading.services.runtime_metrics import (
    RuntimeMetricsTracker,
    config_decimal,
    config_int,
)
from apps.trading.services.unrealized_pnl import update_unrealized_pnl
from apps.trading.tasks.source import TickDataSource
from apps.trading.tasks.state import StateManager
from apps.trading.utils import format_money

logger: Logger = getLogger(name=__name__)

# Backward-compatible export for tests patching this symbol.
EventHandler = _EventHandlerCompat


class StrategyError(Exception):
    """Raised when a strategy signals an error stop.

    This exception is raised by the executor when a strategy returns
    ``should_stop=True`` with ``is_error=True``.  Task runners should
    catch this to transition the task to FAILED with the error message.
    """


def is_forex_market_closed() -> bool:
    """Check if the forex market is currently closed (weekend).

    Forex market closes Friday 21:00 UTC and reopens Sunday 21:00 UTC.

    Delegates to :mod:`apps.trading.services.market_schedule` so the rule
    lives in a single, testable module.  This function is kept for
    backwards compatibility with existing callers and tests.
    """
    from apps.trading.services.market_schedule import is_forex_market_closed as _impl

    return _impl()


@dataclass(slots=True)
class ExecutionLoopState:
    """Mutable loop state for executor runtime."""

    state: ExecutionState
    batch_count: int = 0
    no_tick_batches: int = 0
    max_no_tick_batches: int = 60
    stopped_early: bool = False
    paused_early: bool = False
    stop_reason: str = ""
    is_error: bool = False
    resume_last_tick_timestamp: datetime | None = None
    # Last delivered tick timestamp used for runtime gap detection.  Unlike
    # ``state.last_tick_timestamp`` (which only advances for ticks that were
    # actually processed), this is written *before* we decide whether to
    # process or skip, so it reflects the real cadence of the tick stream.
    last_delivered_tick_timestamp: datetime | None = None


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

        from apps.trading.services.metrics_aggregator import MetricsAggregator

        self._metrics_aggregator = MetricsAggregator(
            task_type=self.task_type.value,
            task_id=str(task.pk),
            execution_id=str(task.execution_id) if task.execution_id else None,
        )
        self._runtime_metrics = self._create_runtime_metrics_tracker()

        # --- Debug: memory profiling ---
        debug_opts = getattr(task, "debug_options", None) or {}
        self._tracemalloc_enabled = bool(debug_opts.get("tracemalloc"))
        self._tracemalloc_started = False
        self._mem_snapshot_count = 0
        self._last_rss_mb = 0

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
            # For trading tasks, fetch live balance from OANDA API.
            # The DB-stored balance may be stale (default 0).
            try:
                from apps.market.services.oanda import OandaService

                client = OandaService(self.task.oanda_account)
                details = client.get_account_details()
                return details.balance
            except Exception as e:
                logger.warning(
                    "Failed to fetch live balance from OANDA for account %s, "
                    "falling back to DB value: %s",
                    self.task.oanda_account.account_id,
                    e,
                )
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

    def _create_runtime_metrics_tracker(self) -> RuntimeMetricsTracker:
        """Create a tracker for strategy-agnostic runtime metrics."""
        task_config = getattr(self.task, "config", None)
        raw_config_dict = getattr(task_config, "config_dict", {}) or {}
        config_dict = raw_config_dict if isinstance(raw_config_dict, dict) else {}
        account_currency = getattr(self.task, "account_currency", "") or getattr(
            getattr(self.task, "oanda_account", None), "currency", ""
        )
        atr_period = config_int(config_dict, "atr_period", 14)

        return RuntimeMetricsTracker(
            instrument=self.instrument,
            pip_size=Decimal(str(self.pip_size)),
            account_currency=str(account_currency or ""),
            margin_rate=config_decimal(config_dict, "margin_rate", "0.04") or Decimal("0.04"),
            atr_period=atr_period,
            atr_baseline_period=(
                config_int(config_dict, "atr_baseline_period", 0)
                if "atr_baseline_period" in config_dict
                else (
                    config_int(config_dict, "atr_baseline_lookback", 0)
                    if "atr_baseline_lookback" in config_dict
                    else None
                )
            ),
            volatility_lock_multiplier=config_decimal(config_dict, "volatility_lock_multiplier"),
            initial_balance=self.initial_balance,
        )

    def handle_events(
        self,
        state: ExecutionState,
        events: List[TradingEvent],
        *,
        replaying: bool = False,
    ) -> None:
        """Handle events from strategy execution.

        Args:
            events: List of TradingEvent instances that were saved
        """
        for trading_event in events:
            if getattr(trading_event, "is_processed", False):
                continue

            replay_classification = self._classify_replay_event(trading_event)
            if replaying:
                logger.warning(
                    "Replaying event - task_id=%s, event_id=%s, event_type=%s, "
                    "strategy_event_type=%s, classification=%s, position_id=%s",
                    self.task.pk,
                    trading_event.pk,
                    trading_event.event_type,
                    (
                        trading_event.details.get("strategy_event_type")
                        if isinstance(trading_event.details, dict)
                        else None
                    ),
                    replay_classification,
                    trading_event.position_id,
                )

            if self.task_type == TaskType.TRADING and self._event_already_applied(
                trading_event=trading_event,
                state=state,
            ):
                self._mark_event_processed(trading_event)
                if replaying:
                    logger.info(
                        "Skipped replayed event already reflected in state - task_id=%s, "
                        "event_id=%s, classification=%s",
                        self.task.pk,
                        trading_event.pk,
                        replay_classification,
                    )
                continue

            try:
                execution_result: EventExecutionResult = (
                    self.event_handler.handle_event_with_replay(
                        trading_event,
                        replaying=replaying,
                    )
                )
                if execution_result.realized_pnl_delta != Decimal("0"):
                    state.current_balance = (
                        Decimal(str(state.current_balance)) + execution_result.realized_pnl_delta
                    )
                    self._runtime_metrics.record_position_closed(
                        execution_result.realized_pnl_delta,
                        realized_pnl_quote=execution_result.realized_pnl_delta_quote,
                    )
                if execution_result.entry_binding is not None:
                    self._runtime_metrics.record_trade()
                self.engine.apply_event_execution_result(
                    state=state,
                    execution_result=execution_result,
                )
                self._mark_event_processed(trading_event)

                if replaying:
                    logger.warning(
                        "Replay applied - task_id=%s, event_id=%s, classification=%s, "
                        "position_ids=%s, order_ids=%s, trade_ids=%s, "
                        "broker_order_ids=%s, oanda_trade_ids=%s",
                        self.task.pk,
                        trading_event.pk,
                        replay_classification,
                        list(execution_result.position_ids),
                        list(execution_result.order_ids),
                        list(execution_result.trade_ids),
                        list(execution_result.broker_order_ids),
                        list(execution_result.oanda_trade_ids),
                    )

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
            except CycleResolutionError as e:
                # Unrecoverable state corruption — record the error on the
                # event and let the exception propagate to stop the task.
                self._mark_event_processing_error(trading_event, str(e))
                raise

        self._refresh_open_positions_cache()

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
        """Flush completed minute-level metric buckets to the database."""
        self._metrics_aggregator.flush()

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
        strategy_type = str(getattr(self.task.config, "strategy_type", "") or "")

        for seq, event in enumerate(events):
            event.sequence_number = seq
            event_type = str(getattr(getattr(event, "event_type", None), "value", event.event_type))
            event_scope = EventType.scope_of(event_type)
            execution_event_type = EventType.execution_event_type_for(event_type)
            requires_execution = EventType.requires_execution(event_type)

            if requires_execution:
                if execution_event_type != event_type:
                    details = event.to_dict()
                    details["strategy_event_type"] = event_type
                    details["event_type"] = execution_event_type
                    trading_record = TradingEvent.from_event(
                        event=event,
                        context=self.event_context,
                        execution_id=self.task.execution_id,
                        strategy_type=strategy_type,
                    )
                    trading_record.event_type = execution_event_type
                    trading_record.severity = "info"
                    trading_record.description = str(details)
                    trading_record.details = details
                    trading_records.append(trading_record)
                else:
                    trading_records.append(
                        TradingEvent.from_event(
                            event=event,
                            context=self.event_context,
                            execution_id=self.task.execution_id,
                            strategy_type=strategy_type,
                        )
                    )

            if event_scope == EventScope.TASK.value and not requires_execution:
                trading_records.append(
                    TradingEvent.from_event(
                        event=event,
                        context=self.event_context,
                        execution_id=self.task.execution_id,
                        strategy_type=strategy_type,
                    )
                )
            elif event_scope == EventScope.STRATEGY.value:
                strategy_records.append(
                    StrategyEventRecord.from_event(
                        event=event,
                        context=self.event_context,
                        execution_id=self.task.execution_id,
                        strategy_type=strategy_type,
                    )
                )

        if trading_records:
            TradingEvent.objects.bulk_create(trading_records)
        if strategy_records:
            StrategyEventRecord.objects.bulk_create(strategy_records)

        return trading_records

    def execute(self) -> None:
        """Execute the task."""
        if self._tracemalloc_enabled:
            self._start_tracemalloc()
        try:
            state, resumed = self._start_execution()
            loop = ExecutionLoopState(
                state=state,
                resume_last_tick_timestamp=(state.last_tick_timestamp if resumed else None),
            )
            # Market-aware idle gate: if the task is a live trading task and
            # the forex market is currently closed, switch to IDLE before
            # waiting for ticks. This gives the user an immediate visual
            # signal that the task is parked rather than showing RUNNING
            # while the tick source is quiet.
            self._maybe_enter_market_idle_at_start(loop)
            self._run_tick_loop(loop)
            self._finalize_execution(loop)
        except Exception as e:
            self._handle_execution_failure(e)
            raise
        finally:
            if self._tracemalloc_started:
                self._stop_tracemalloc()
            self._cleanup_execution()

    def _maybe_enter_market_idle_at_start(self, loop: ExecutionLoopState) -> None:
        """Switch to IDLE right after start if the market is already closed.

        Only applies to live trading tasks. This is a cheap pre-flight check:
        the tick loop will maintain the RUNNING ↔ IDLE transitions on its
        own once batches start arriving.
        """
        if self.task_type != TaskType.TRADING:
            return
        if not is_forex_market_closed():
            return
        # Reuse the shared entry helper so the status change and the
        # in-state ``_idle_entered_at`` marker stay consistent with what
        # happens later in the tick loop.
        self._maybe_enter_market_idle(loop)

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

    def _start_execution(self) -> tuple[ExecutionState, bool]:
        """Initialize coordinator/state and run strategy start hook.

        Returns:
            Tuple of (state, resumed) where resumed indicates whether this
            execution is continuing from a previous run.
        """
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
        self._refresh_open_positions_cache()

        # Restore cumulative metric counters from DB when resuming a live
        # trading task.  Backtest restarts always start fresh — the caller
        # allocates a new execution_id and the task is expected to replay
        # from ``task.start_time``, so there is nothing to restore.
        if resumed:
            self._restore_metric_counters()

        logger.info("Engine started, events_count=%d", len(result.events))
        self._persist_config_snapshot()
        return state, resumed

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
            self._after_batch_processed(loop)

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
        should_stop = getattr(control, "should_stop", False) is True
        should_pause = getattr(control, "should_pause", False) is True
        if should_stop:
            logger.info("Stop signal received - ticks_processed=%d", loop.state.ticks_processed)
            loop.stopped_early = True
            return True

        if not should_pause:
            return False

        logger.info("Pause signal received - ticks_processed=%d", loop.state.ticks_processed)
        loop.paused_early = True
        return True

    def _after_batch_processed(self, loop: ExecutionLoopState) -> None:
        """Hook for executor-specific checks after each processed batch."""
        _ = loop

    def _handle_empty_batch(self, loop: ExecutionLoopState) -> bool:
        """Handle empty tick batch; return True when loop should terminate."""
        if self.task_type == TaskType.TRADING and is_forex_market_closed():
            if loop.no_tick_batches == 0:
                logger.info("Market is closed, tolerating empty batches")
            loop.no_tick_batches = 0
            self._maybe_enter_market_idle(loop)
            return False

        loop.no_tick_batches += 1
        if self.task_type == TaskType.TRADING:
            # Market is open — if we were idling, exit idle (possibly after
            # the configured resume delay) back to RUNNING.
            self._maybe_exit_market_idle(loop)
            if loop.no_tick_batches == loop.max_no_tick_batches:
                logger.warning(
                    "No ticks received for %d consecutive batches on live trading task. "
                    "Keeping task alive and waiting for the market data stream to resume.",
                    loop.no_tick_batches,
                )
            elif (
                loop.no_tick_batches > loop.max_no_tick_batches
                and loop.no_tick_batches % loop.max_no_tick_batches == 0
            ):
                logger.warning(
                    "Still waiting for live ticks after %d consecutive empty batches.",
                    loop.no_tick_batches,
                )
            return False

        if loop.no_tick_batches < loop.max_no_tick_batches:
            return False

        logger.warning(
            "No ticks received for %d consecutive batches. Data source may have ended without EOF signal.",
            loop.no_tick_batches,
        )
        return True

    def _process_tick_batch(self, loop: ExecutionLoopState, tick_batch: list) -> None:
        """Process one non-empty batch."""
        # Drain-on-stop integration: when the task is DRAINING, inspect open
        # positions and close any at breakeven-or-better *before* feeding
        # ticks into the strategy, so that closed positions are reflected in
        # the same batch instead of the next one.  This also lets us exit
        # the loop as soon as the drain is complete.
        if self._handle_drain_pre_batch(loop):
            return
        for tick_idx, tick in enumerate(tick_batch):
            if tick_idx % 100 == 0 and self._should_stop_during_batch(loop, tick_idx):
                break
            if self._process_single_tick(loop, tick):
                break

    # ------------------------------------------------------------------
    # Drain-on-stop
    # ------------------------------------------------------------------

    def _handle_drain_pre_batch(self, loop: ExecutionLoopState) -> bool:
        """Advance the drain state machine. Returns True when execution should stop."""
        if self.task_type != TaskType.TRADING:
            return False
        task = cast(TradingTask, self.task)
        task.refresh_from_db(fields=["status"])
        if task.status != TaskStatus.DRAINING:
            return False

        from apps.trading.services.drain import DrainCandidate, DrainPolicy

        drain_marker = self._read_drain_marker(loop)
        now = dj_timezone.now()
        if drain_marker is None:
            drain_marker = now
            self._record_drain_marker(loop, drain_marker)

        duration_hours = int(getattr(task, "drain_duration_hours", 0) or 0)
        policy = DrainPolicy(
            drain_started_at=drain_marker,
            duration_hours=duration_hours,
        )

        open_positions = self.order_service.get_open_positions(instrument=self.instrument)
        candidates: list[DrainCandidate] = []
        for position in open_positions:
            unrealized = getattr(position, "unrealized_pnl", None)
            try:
                unrealized_dec = (
                    unrealized if isinstance(unrealized, Decimal) else Decimal(str(unrealized))
                )
            except (TypeError, ValueError, InvalidOperation):
                unrealized_dec = Decimal("0")
            candidates.append(
                DrainCandidate(
                    position_id=str(position.pk),
                    current_unrealized_pnl=unrealized_dec,
                )
            )

        decision = policy.evaluate(now=now, open_positions=candidates)

        for position_id in decision.close_position_ids:
            self._close_position_during_drain(position_id)

        if decision.should_finalize:
            logger.info(
                "Drain complete - task_id=%s, reason=%s",
                task.pk,
                decision.finalize_reason,
            )
            loop.stopped_early = True
            loop.stop_reason = decision.finalize_reason or "drain_complete"
            self._record_drain_marker(loop, None)
            return True

        return False

    def _close_position_during_drain(self, position_id: str) -> None:
        """Close a single position; errors are logged and swallowed."""
        from apps.trading.models import Position

        try:
            position = Position.objects.get(pk=position_id, is_open=True)
        except Position.DoesNotExist:  # pragma: no cover - race with close
            return
        try:
            self.order_service.close_position(position=position)
        except OrderServiceError as exc:
            logger.warning(
                "Drain close failed - position_id=%s, error=%s",
                position_id,
                exc,
            )

    def _close_all_positions_on_stop_if_requested(self, loop: ExecutionLoopState) -> None:
        """Close every open position when ``sell_on_stop`` was requested.

        Called once, at the start of ``_finalize_execution``, right before the
        strategy's on_stop hook runs.  Applies to both live trading and
        backtest tasks.  Each close goes through ``OrderService`` so the
        correct broker-vs-simulated behaviour applies (OANDA market close
        for trading, tick-priced close for backtest).
        """
        self.task.refresh_from_db(fields=["sell_on_stop"])
        if not getattr(self.task, "sell_on_stop", False):
            return

        open_positions = self.order_service.get_open_positions(instrument=self.instrument)
        if not open_positions:
            logger.info(
                "sell_on_stop requested but no open positions - task_id=%s",
                self.task.pk,
            )
            return

        logger.info(
            "Closing %d open position(s) on stop - task_id=%s",
            len(open_positions),
            self.task.pk,
        )
        for position in open_positions:
            try:
                self.order_service.close_position(position=position)
            except OrderServiceError as exc:
                logger.warning(
                    "sell_on_stop close failed - task_id=%s, position_id=%s, error=%s",
                    self.task.pk,
                    getattr(position, "pk", None),
                    exc,
                )
        self._refresh_open_positions_cache()

    def _record_drain_marker(self, loop: ExecutionLoopState, started_at: datetime | None) -> None:
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        if started_at is None:
            strategy_state.pop("_drain_started_at", None)
        else:
            strategy_state["_drain_started_at"] = started_at.isoformat()
        loop.state.strategy_state = strategy_state
        try:
            loop.state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:  # pragma: no cover
            logger.debug("Failed to persist drain marker", exc_info=True)

    def _read_drain_marker(self, loop: ExecutionLoopState) -> datetime | None:
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        raw = strategy_state.get("_drain_started_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Market-aware idle (trading tasks only)
    # ------------------------------------------------------------------

    def _maybe_enter_market_idle(self, loop: ExecutionLoopState) -> None:
        """Transition a live trading task to IDLE when the market is closed.

        Safe to call every loop iteration: the method is idempotent and
        short-circuits for non-trading tasks or tasks already in IDLE.
        """
        if self.task_type != TaskType.TRADING:
            return
        task = cast(TradingTask, self.task)
        task.refresh_from_db(fields=["status"])
        if task.status != TaskStatus.RUNNING:
            return
        # Transition to IDLE and persist the idle-start marker.
        type(task).objects.filter(pk=task.pk, status=TaskStatus.RUNNING).update(
            status=TaskStatus.IDLE,
            updated_at=dj_timezone.now(),
        )
        task.refresh_from_db(fields=["status"])
        logger.info("Trading task switched to IDLE (market closed) - task_id=%s", task.pk)
        self._record_idle_marker(loop, dj_timezone.now())

    def _maybe_exit_market_idle(self, loop: ExecutionLoopState) -> None:
        """Resume a live trading task from IDLE once the market reopens.

        Honours the optional ``market_idle_resume_delay_minutes`` field so
        callers don't start trading into the very first ticks of the
        session.
        """
        if self.task_type != TaskType.TRADING:
            return
        task = cast(TradingTask, self.task)
        task.refresh_from_db(fields=["status"])
        if task.status != TaskStatus.IDLE:
            return

        from apps.trading.services.market_schedule import should_resume_from_idle

        delay_minutes = int(getattr(task, "market_idle_resume_delay_minutes", 0) or 0)
        idle_marker = self._read_idle_marker(loop)
        if not should_resume_from_idle(
            now=dj_timezone.now(),
            idle_entered_at=idle_marker,
            resume_delay_minutes=delay_minutes,
        ):
            return

        type(task).objects.filter(pk=task.pk, status=TaskStatus.IDLE).update(
            status=TaskStatus.RUNNING,
            updated_at=dj_timezone.now(),
        )
        task.refresh_from_db(fields=["status"])
        logger.info("Trading task resumed from IDLE (market open) - task_id=%s", task.pk)
        self._record_idle_marker(loop, None)

    def _record_idle_marker(self, loop: ExecutionLoopState, entered_at: datetime | None) -> None:
        """Persist the idle-start timestamp into ExecutionState."""
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        if entered_at is None:
            strategy_state.pop("_idle_entered_at", None)
        else:
            strategy_state["_idle_entered_at"] = entered_at.isoformat()
        loop.state.strategy_state = strategy_state
        try:
            loop.state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:  # pragma: no cover - best effort persistence
            logger.debug("Failed to persist idle marker", exc_info=True)

    def _read_idle_marker(self, loop: ExecutionLoopState) -> datetime | None:
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        raw = strategy_state.get("_idle_entered_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    def _should_stop_during_batch(self, loop: ExecutionLoopState, tick_idx: int) -> bool:
        """Check stop signal during long batch processing."""
        control = self.state_manager.check_control()
        should_stop = getattr(control, "should_stop", False) is True
        should_pause = getattr(control, "should_pause", False) is True
        if should_stop:
            logger.info(
                "Stop signal received during batch processing - task_id=%s, task_type=%s, ticks_processed=%d, tick_idx=%d",
                self.task.pk,
                self.task_type.value,
                loop.state.ticks_processed,
                tick_idx,
            )
            loop.stopped_early = True
            return True

        if not should_pause:
            return False

        logger.info(
            "Pause signal received during batch processing - task_id=%s, task_type=%s, ticks_processed=%d, tick_idx=%d",
            self.task.pk,
            self.task_type.value,
            loop.state.ticks_processed,
            tick_idx,
        )
        loop.paused_early = True
        return True

    def _process_single_tick(self, loop: ExecutionLoopState, tick) -> bool:
        """Process one tick; return True when execution should stop."""
        # Skip ticks already processed in a previous run (resume scenario).
        # last_tick_timestamp is persisted after each tick, so any tick at or
        # before that timestamp has already been fully handled.
        # However, we still feed skipped ticks into the runtime metrics tracker
        # so that rolling calculations (ATR, candle history) are warmed up
        # before the first "real" tick after resume.
        # Runtime gap detection (backtest only): abort the run if the tick
        # stream jumps forward by more than MARKET_BACKTEST_MAX_TICK_GAP_HOURS
        # and the gap is not explained by a forex weekend close.  Historically
        # this symptom was caused by Redis pub/sub silently dropping messages
        # when the subscriber lagged; we now deliver ticks via Redis Streams
        # (reliable), but this guard remains as defence-in-depth so silent
        # data loss can never go unnoticed.
        if self.task_type == TaskType.BACKTEST and loop.last_delivered_tick_timestamp is not None:
            delivered_ts = self._coerce_tick_timestamp(tick.timestamp)
            if delivered_ts is not None and self._is_suspicious_tick_gap(
                loop.last_delivered_tick_timestamp, delivered_ts
            ):
                gap = delivered_ts - loop.last_delivered_tick_timestamp
                msg = (
                    "Suspicious tick gap detected in backtest stream - "
                    f"previous_ts={loop.last_delivered_tick_timestamp}, "
                    f"current_ts={delivered_ts}, gap={gap}. "
                    "This usually indicates silent message loss; aborting to "
                    "prevent a corrupted backtest result."
                )
                logger.error(msg)
                loop.stopped_early = True
                loop.stop_reason = f"tick_gap:{gap.total_seconds():.0f}s"
                loop.is_error = True
                return True

        resume_ts = loop.resume_last_tick_timestamp
        if resume_ts is not None:
            tick_ts = self._coerce_tick_timestamp(tick.timestamp)
            if tick_ts is not None and tick_ts <= resume_ts:
                # Warm up metrics tracker with skipped ticks
                self._runtime_metrics._record_tick(
                    timestamp=tick_ts,
                    mid=Decimal(str(tick.mid)),
                )
                loop.last_delivered_tick_timestamp = tick_ts
                return False

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
            loop.stop_reason = result.stop_reason
            loop.is_error = result.is_error
            return True

        tick_timestamp = self._coerce_tick_timestamp(tick.timestamp)
        loop.state.ticks_processed += 1
        loop.state.last_tick_timestamp = tick_timestamp
        loop.state.last_tick_price = tick.mid
        loop.state.last_tick_bid = tick.bid
        loop.state.last_tick_ask = tick.ask
        loop.last_delivered_tick_timestamp = tick_timestamp
        self._update_common_metrics(loop.state, tick)
        self._buffer_tick_metrics(loop.state, tick)
        return False

    @staticmethod
    def _coerce_tick_timestamp(value) -> datetime:
        """Normalize tick timestamps to timezone-aware datetimes."""
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

        timestamp_str = str(value).strip()
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        parsed = datetime.fromisoformat(timestamp_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _is_suspicious_tick_gap(previous: datetime, current: datetime) -> bool:
        """Return True when ``current`` jumps forward from ``previous`` by an
        amount that cannot be explained by forex market hours.

        The threshold is configured by
        ``settings.MARKET_BACKTEST_MAX_TICK_GAP_HOURS`` (default 72 hours).
        The regular weekend close (Fri 21:00 → Sun 21:00 UTC) is always
        considered acceptable.
        """
        from datetime import timedelta

        from django.conf import settings as _settings

        if current <= previous:
            return False

        max_gap_hours = int(getattr(_settings, "MARKET_BACKTEST_MAX_TICK_GAP_HOURS", 72))
        gap = current - previous
        if gap <= timedelta(hours=max_gap_hours):
            return False

        # Forex weekend close: last tick on Fri evening ≥20:00 UTC and
        # current on Sunday evening or Monday morning UTC.  Allow up to
        # ~3 days total to cover holidays that extend the closure.
        lt_weekday = previous.weekday()
        if lt_weekday == 4 and previous.hour >= 20:
            if gap < timedelta(days=3, hours=12):
                return False

        return True

    def _refresh_open_positions_cache(self) -> None:
        """Refresh cached open positions used by common metric calculation."""
        positions = self.order_service.get_open_positions(instrument=self.instrument)
        self._runtime_metrics.sync_open_positions(positions)

    def _restore_metric_counters(self) -> None:
        """Restore cumulative metric counters from DB for resumed executions."""
        from django.db.models import Case, F, Sum, Value, When

        from apps.trading.models.positions import Position
        from apps.trading.models.trades import Trade

        base_filter: dict = {
            "task_type": self.task_type.value,
            "task_id": str(self.task.pk),
        }
        if self.task.execution_id:
            base_filter["execution_id"] = self.task.execution_id

        abs_units = Case(When(units__lt=0, then=-F("units")), default=F("units"))

        closed_qs = Position.objects.filter(**base_filter, is_open=False).exclude(
            exit_price__isnull=True
        )
        agg = closed_qs.aggregate(
            realized_pnl=Sum(
                Case(
                    When(direction="long", then=(F("exit_price") - F("entry_price")) * abs_units),
                    When(direction="short", then=(F("entry_price") - F("exit_price")) * abs_units),
                    default=Value(Decimal("0")),
                )
            ),
            winning=Sum(
                Case(
                    When(
                        direction="long",
                        then=Case(
                            When(exit_price__gt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    When(
                        direction="short",
                        then=Case(
                            When(exit_price__lt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    default=Value(0),
                )
            ),
            losing=Sum(
                Case(
                    When(
                        direction="long",
                        then=Case(
                            When(exit_price__lt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    When(
                        direction="short",
                        then=Case(
                            When(exit_price__gt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    default=Value(0),
                )
            ),
        )

        self._runtime_metrics.restore_counters(
            realized_pnl=agg["realized_pnl"] or Decimal("0"),
            total_trades=Trade.objects.filter(
                **base_filter, execution_method="open_position"
            ).count(),
            closed_positions=closed_qs.count(),
            winning_trades=agg["winning"] or 0,
            losing_trades=agg["losing"] or 0,
        )

    def _update_common_metrics(self, state: ExecutionState, tick) -> None:
        """Merge strategy-agnostic runtime metrics into state.strategy_state.metrics."""
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        existing_metrics = (
            dict(strategy_state.get("metrics", {}))
            if isinstance(strategy_state.get("metrics"), dict)
            else {}
        )
        try:
            current_balance = Decimal(str(state.current_balance))
        except (InvalidOperation, TypeError, ValueError):
            current_balance = Decimal("0")
        common_metrics = self._runtime_metrics.build_metrics(
            timestamp=self._coerce_tick_timestamp(tick.timestamp),
            bid=Decimal(str(tick.bid)),
            ask=Decimal(str(tick.ask)),
            mid=Decimal(str(tick.mid)),
            current_balance=current_balance,
            ticks_processed=state.ticks_processed,
        )
        existing_metrics.update(common_metrics)
        strategy_state["metrics"] = existing_metrics
        state.strategy_state = strategy_state

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
        self.handle_events(state, pending_events, replaying=True)
        self.save_state(state)

    @staticmethod
    def _classify_replay_event(trading_event: TradingEvent) -> str:
        """Classify replayed events by potential PnL impact."""
        trade_impacting = {
            "open_position",
            "close_position",
            "rebuild_position",
            "volatility_lock",
            "volatility_hedge_neutralize",
            "margin_protection",
        }
        return "trade-impacting" if trading_event.event_type in trade_impacting else "lifecycle"

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
        """Record strategy metrics into the minute-level aggregator."""
        metrics = (state.strategy_state or {}).get("metrics", {})
        if not metrics:
            return
        self._metrics_aggregator.record(self._coerce_tick_timestamp(tick.timestamp), metrics)

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
        if self._tracemalloc_enabled:
            self._check_memory(loop)

    def _update_unrealized_pnl(self, state: ExecutionState) -> None:
        """Recalculate unrealized pnl for open positions from latest tick."""
        if state.last_tick_bid is None or state.last_tick_ask is None:
            return

        update_unrealized_pnl(
            task_type=self.task_type.value,
            task_id=str(self.task.pk),
            bid_price=Decimal(str(state.last_tick_bid)),
            ask_price=Decimal(str(state.last_tick_ask)),
            execution_id=self.task.execution_id,
        )

    def _emit_batch_telemetry(self, loop: ExecutionLoopState) -> None:
        """Emit periodic progress logs and heartbeat updates."""
        if loop.batch_count % 50 == 0:
            logger.debug(
                "Metrics progress - task_id=%s, batch=%d, ticks_processed=%d, pending_buckets=%d, last_tick_ts=%s",
                self.task.pk,
                loop.batch_count,
                loop.state.ticks_processed,
                len(self._metrics_aggregator._buckets),
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

    # ------------------------------------------------------------------
    # Debug: memory profiling (opt-in via task.debug_options.tracemalloc)
    # ------------------------------------------------------------------

    def _start_tracemalloc(self) -> None:
        import tracemalloc

        if tracemalloc.is_tracing():
            logger.info("[TRACEMALLOC] Already tracing, reusing")
        else:
            tracemalloc.start(25)
        self._tracemalloc_started = True
        logger.warning(
            "[TRACEMALLOC] Enabled for task %s — expect CPU/memory overhead",
            self.task.pk,
        )

    def _stop_tracemalloc(self) -> None:
        import tracemalloc

        if tracemalloc.is_tracing():
            self._log_tracemalloc_snapshot("final")
            tracemalloc.stop()
        self._tracemalloc_started = False
        logger.info("[TRACEMALLOC] Stopped for task %s", self.task.pk)

    def _check_memory(self, loop: ExecutionLoopState) -> None:
        """Log RSS and take tracemalloc snapshot when memory grows."""
        import resource

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS returns bytes, Linux returns KB
        import sys

        rss_mb = rss_kb // 1024 if sys.platform == "linux" else rss_kb // (1024 * 1024)

        # Log RSS every 100 batches (~10k ticks)
        if loop.batch_count % 100 == 0:
            logger.info(
                "[MEMORY] task=%s batch=%d ticks=%d rss=%dMB",
                self.task.pk,
                loop.batch_count,
                loop.state.ticks_processed,
                rss_mb,
            )

        # Take snapshot when RSS jumps by 500MB+ since last snapshot
        if rss_mb - self._last_rss_mb >= 500:
            self._mem_snapshot_count += 1
            self._log_tracemalloc_snapshot(
                f"rss_jump_{self._mem_snapshot_count}",
            )
            self._last_rss_mb = rss_mb

    def _log_tracemalloc_snapshot(self, label: str) -> None:
        """Take a tracemalloc snapshot and log the top allocations."""
        import tracemalloc

        if not tracemalloc.is_tracing():
            return

        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")

        current, peak = tracemalloc.get_traced_memory()
        logger.warning(
            "[TRACEMALLOC:%s] task=%s current=%.1fMB peak=%.1fMB",
            label,
            self.task.pk,
            current / (1024 * 1024),
            peak / (1024 * 1024),
        )
        for i, stat in enumerate(stats[:20]):
            logger.warning("[TRACEMALLOC:%s] #%d %s", label, i + 1, stat)

    def _finalize_execution(self, loop: ExecutionLoopState) -> None:
        """Run stop hook and persist final stop state."""
        # If the user asked for "Close All Positions" at stop time, close
        # them here before the strategy's on_stop hook runs so that the
        # final balance and metrics reflect the closed positions.  Applies
        # to both live trading and backtest tasks.
        self._close_all_positions_on_stop_if_requested(loop)
        logger.info("Calling engine.on_stop")
        result = self.engine.on_stop(state=loop.state)
        loop.state = result.state
        self.save_events(result.events)
        self.save_state(loop.state)
        # Flush any remaining metrics (including the last partial minute)
        self._metrics_aggregator.flush(final=True)
        logger.info("Engine stopped, events_count=%d", len(result.events))

        if loop.stopped_early and loop.is_error:
            logger.error(
                "Execution failed: %s — ticks_processed=%d, final_balance=%s",
                loop.stop_reason,
                loop.state.ticks_processed,
                format_money(loop.state.current_balance),
            )
            self.state_manager.stop(
                status_message=f"Execution failed: {loop.stop_reason}",
            )
            raise StrategyError(loop.stop_reason)

        if loop.paused_early:
            logger.info(
                "Execution paused - ticks_processed=%d, final_balance=%s",
                loop.state.ticks_processed,
                loop.state.current_balance,
            )
            type(self.task).objects.filter(
                pk=self.task.pk,
                status__in=(TaskStatus.RUNNING, TaskStatus.PAUSED),
            ).update(
                status=TaskStatus.PAUSED,
                completed_at=None,
            )
            self.task.refresh_from_db()
            self.state_manager.pause(status_message="Execution paused")
            return

        if loop.stopped_early:
            logger.info(
                "Execution stopped by external signal - ticks_processed=%d, final_balance=%s",
                loop.state.ticks_processed,
                loop.state.current_balance,
            )
            self.state_manager.stop(status_message="Execution stopped by external signal")
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

    def _persist_config_snapshot(self) -> None:
        """Save task and strategy config into the execution snapshot early.

        Called at execution start so the config is captured even if the
        execution fails before reaching the finalization step.
        """
        from apps.trading.models import TaskExecutionSnapshot
        from apps.trading.services.execution_snapshots import (
            _snapshot_strategy_config,
            _snapshot_task_config,
        )

        execution_id = getattr(self.task, "execution_id", None)
        if execution_id is None:
            return
        try:
            TaskExecutionSnapshot.objects.update_or_create(
                task_type=self.task_type.value,
                task_id=self.task.pk,
                execution_id=execution_id,
                defaults={
                    "task_config": _snapshot_task_config(self.task),
                    "strategy_config": _snapshot_strategy_config(self.task),
                },
            )
        except Exception:
            logger.warning("Failed to persist config snapshot", exc_info=True)

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

    _RUNTIME_DRIFT_CHECK_EVERY_BATCHES = 5

    def _after_batch_processed(self, loop: ExecutionLoopState) -> None:
        super()._after_batch_processed(loop)
        trading_task = cast(TradingTask, self.task)
        if getattr(trading_task, "dry_run", False):
            return
        if loop.batch_count % self._RUNTIME_DRIFT_CHECK_EVERY_BATCHES != 0:
            return
        self._assert_runtime_broker_sync(state=loop.state)

    def _assert_runtime_broker_sync(self, *, state: ExecutionState) -> None:
        """Fail fast when broker exposure drifts during a live execution."""
        trading_task = cast(TradingTask, self.task)
        from apps.trading.services.reconciliation import TradingResumeReconciler, TradingSafetyError

        reconciler = TradingResumeReconciler(
            task=trading_task,
            state=state,
        )
        report = reconciler.detect_runtime_drift()
        if not report.has_blockers:
            return

        for blocker in report.blockers:
            logger.error(
                "Live broker drift detected - task_id=%s, execution_id=%s, blocker=%s",
                self.task.pk,
                self.task.execution_id,
                blocker,
            )
        raise TradingSafetyError(
            "Trading task stopped because broker state drift was detected while it was running. "
            "Review task logs and reconcile the OANDA account before restarting."
        )

    def prepare_state_for_execution(
        self,
        *,
        state: ExecutionState,
        resumed: bool,
    ) -> ExecutionState:
        """Reconcile broker/local state before live trading starts or resumes."""
        trading_task = cast(TradingTask, self.task)
        if getattr(trading_task, "dry_run", False):
            return state

        from apps.trading.services.reconciliation import TradingResumeReconciler, TradingSafetyError

        reconciler = TradingResumeReconciler(
            task=trading_task,
            state=state,
        )
        report = reconciler.reconcile(resumed=resumed)
        if report.has_blockers:
            for blocker in report.blockers:
                logger.error(
                    "Trading safety blocker - task_id=%s, execution_id=%s, blocker=%s",
                    self.task.pk,
                    self.task.execution_id,
                    blocker,
                )
            raise TradingSafetyError(
                "Trading task blocked by broker reconciliation safety checks. "
                "Review task logs and reconcile the OANDA account before restarting."
            )

        lifecycle = "resume" if resumed else "start"
        logger.info(
            "Trading %s reconciliation complete - task_id=%s, execution_id=%s, "
            "open_trades=%d, pending_orders=%d, closed_local=%d, created_local=%d, "
            "updated_local=%d, removed_entries=%d, synthesized_entries=%d, relinked_entries=%d",
            lifecycle,
            self.task.pk,
            self.task.execution_id,
            report.broker_open_positions,
            report.pending_broker_orders,
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
