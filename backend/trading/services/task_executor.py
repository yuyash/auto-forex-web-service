"""
Task execution service for backtest and trading tasks.

This module provides functions for executing backtest and trading tasks,
handling TaskExecution creation, status updates, and ExecutionMetrics generation.

Requirements: 4.1, 4.2, 4.3, 4.6, 4.8, 7.3, 7.4, 7.5, 4.7, 4.9
"""

# pylint: disable=too-many-lines

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Generator

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from trading.backtest_engine import BacktestConfig, BacktestEngine
from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus, TaskType
from trading.execution_models import ExecutionMetrics, TaskExecution
from trading.historical_data_loader import HistoricalDataLoader
from trading.strategy_registry import registry
from trading.trading_task_models import TradingTask
from trading_system.config_loader import get_config

logger = logging.getLogger(__name__)

# Lock timeout in seconds (default: 1 hour)
LOCK_TIMEOUT = 3600
# Lock key prefix
LOCK_KEY_PREFIX = "task_execution_lock:"


def _load_backtest_data(task: BacktestTask, data_loader: Any) -> tuple[list[Any], str | None]:
    """
    Load historical data for backtest task.

    Args:
        task: BacktestTask instance
        data_loader: HistoricalDataLoader instance

    Returns:
        Tuple of (tick_data, error_message)
    """
    logger.info(
        "Loading historical data for %s from %s to %s",
        task.instrument,
        task.start_time,
        task.end_time,
    )

    tick_data = []

    # Use the instrument from the task model (string field)
    instrument_data = data_loader.load_data(
        instrument=task.instrument,
        start_date=task.start_time,
        end_date=task.end_time,
    )
    tick_data.extend(instrument_data)

    # Sort by timestamp
    tick_data.sort(key=lambda t: t.timestamp)

    if not tick_data:
        return [], "No historical data available for the specified period"

    logger.info("Loaded %d tick data points", len(tick_data))
    return tick_data, None


def _load_backtest_data_by_day(
    task: BacktestTask, data_loader: Any, current_date: datetime
) -> tuple[list[Any], str | None]:
    """
    Load historical data for a single day.

    Args:
        task: BacktestTask instance
        data_loader: HistoricalDataLoader instance
        current_date: Date to load data for

    Returns:
        Tuple of (tick_data, error_message)
    """
    # Set start and end times for the day
    day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)

    # Don't exceed the task's end time
    day_end = min(day_end, task.end_time)

    logger.info(
        "Loading data for %s on %s",
        task.instrument,
        current_date.strftime("%Y-%m-%d"),
    )

    # Load data for this day
    instrument_data = data_loader.load_data(
        instrument=task.instrument,
        start_date=day_start,
        end_date=day_end,
    )

    # Sort by timestamp
    instrument_data.sort(key=lambda t: t.timestamp)

    logger.info(
        "Loaded %d tick data points for %s", len(instrument_data), current_date.strftime("%Y-%m-%d")
    )
    return instrument_data, None


def _log_strategy_events_to_execution(  # pylint: disable=too-many-locals,too-many-statements
    execution: TaskExecution,
    engine: BacktestEngine,
    last_event_index: int,
) -> int:
    """
    Log new strategy events to execution logs.

    This function captures floor strategy events (initial entry, retracement,
    close, take profit, etc.) and adds them to the execution logs for display
    in the frontend TaskExecutionsTab.

    Args:
        execution: TaskExecution instance to add logs to
        engine: BacktestEngine instance with strategy
        last_event_index: Index of last logged event (to avoid duplicates)

    Returns:
        New last_event_index after logging
    """
    if not engine.strategy or not hasattr(engine.strategy, "_backtest_events"):
        return last_event_index

    def _parse_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    events = engine.strategy._backtest_events  # pylint: disable=protected-access

    # Log new events since last check
    for i in range(last_event_index, len(events)):
        event = events[i]
        event_type = event.get("event_type", "unknown")
        description = event.get("description", "")
        details = event.get("details", {})

        # Format message based on event type for floor strategy
        detail_event_type = details.get("event_type", "")

        if detail_event_type == "initial":
            # Initial entry event
            direction = details.get("direction", "").upper()
            units = details.get("units", "")
            price = details.get("price", "")
            layer = details.get("layer", 1)
            execution.add_log(
                "INFO",
                f"[FLOOR] Layer {layer} Initial Entry: {direction} {units} units @ {price}",
            )
        elif detail_event_type == "retracement":
            # Retracement/scale-in event
            direction = details.get("direction", "").upper()
            units = details.get("units", "")
            price = details.get("price", "")
            layer = details.get("layer", 1)
            retracement_count = details.get("retracement_count", 0)
            execution.add_log(
                "INFO",
                f"[FLOOR] Layer {layer} Retracement #{retracement_count}: "
                f"{direction} {units} units @ {price}",
            )
        elif detail_event_type == "layer":
            # Retracement detection events are noisy; skip logging to avoid redundant UI spam.
            continue
        elif detail_event_type in ("close", "take_profit", "volatility_lock", "margin_protection"):
            # Close events
            direction = details.get("direction", "").upper()
            units = details.get("units", "")
            entry_price = details.get("entry_price", "")
            exit_price = details.get("exit_price", "")
            pnl = details.get("pnl", 0)
            reason_display = details.get(
                "reason_display", detail_event_type.replace("_", " ").title()
            )
            layer = details.get("layer_number", details.get("layer", ""))

            entry_retracement = _parse_int(details.get("entry_retracement_count"))
            remaining_retracements = _parse_int(details.get("retracement_count"))
            retracement_info_parts = []
            if entry_retracement is not None:
                retracement_info_parts.append(f"Entry Retracement #{entry_retracement}")
            if remaining_retracements is not None:
                retracement_info_parts.append(f"Remaining Retracements: {remaining_retracements}")
            retracement_suffix = (
                f" ({', '.join(retracement_info_parts)})" if retracement_info_parts else ""
            )

            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            layer_str = f"Layer {layer} " if layer else ""
            execution.add_log(
                "INFO",
                f"[FLOOR] {layer_str}{reason_display}: {direction} {units} units, "
                f"Entry: {entry_price} → Exit: {exit_price}, P&L: {pnl_str}{retracement_suffix}",
            )
        elif event_type == "entry_signal_triggered":
            # Entry signal event (optional - can be verbose)
            pass  # Skip to reduce log noise
        elif event_type in ("start_strategy", "end_strategy"):
            # Strategy lifecycle events - already logged elsewhere
            pass
        elif event_type == "retracement_detected":
            # Already handled by 'layer' event_type above
            pass
        else:
            # Log other events with their description
            if description and event_type not in ("no_entry_signal", "inactive_instrument"):
                execution.add_log("INFO", f"[FLOOR] {description}")

    return len(events)


# Maximum number of equity curve points to store (for chart display)
MAX_EQUITY_CURVE_POINTS = 1000


def _downsample_equity_curve(equity_curve: list, max_points: int = MAX_EQUITY_CURVE_POINTS) -> list:
    """
    Downsample equity curve to reduce storage size while preserving chart shape.

    Uses LTTB (Largest Triangle Three Buckets) inspired algorithm that preserves
    important points like peaks and troughs.

    Args:
        equity_curve: List of equity point dicts with 'timestamp' and 'balance' keys
        max_points: Maximum number of points to keep

    Returns:
        Downsampled list of equity points
    """
    if len(equity_curve) <= max_points:
        return equity_curve

    # Always keep first and last points
    result = [equity_curve[0]]

    # Calculate bucket size (excluding first and last)
    bucket_size = (len(equity_curve) - 2) / (max_points - 2)

    for i in range(1, max_points - 1):
        # Calculate bucket boundaries
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = int(i * bucket_size) + 1
        bucket_end = min(bucket_end, len(equity_curve) - 1)

        # Find point with max balance change in bucket (preserves peaks/troughs)
        # Note: EquityPoint.to_dict() uses 'balance' key, not 'equity'
        best_point = equity_curve[bucket_start]
        max_change = 0

        prev_balance = result[-1].get("balance", 0)
        for j in range(bucket_start, bucket_end):
            point = equity_curve[j]
            change = abs(point.get("balance", 0) - prev_balance)
            if change > max_change:
                max_change = change
                best_point = point

        result.append(best_point)

    # Add last point
    result.append(equity_curve[-1])

    return result


def _create_execution_metrics(
    execution: TaskExecution,
    performance_metrics: dict[str, Any],
    equity_curve: list,
    trade_log: list,
) -> ExecutionMetrics:
    """
    Create ExecutionMetrics from backtest results.

    Args:
        execution: TaskExecution instance
        performance_metrics: Performance metrics dictionary
        equity_curve: List of EquityPoint objects or dicts
        trade_log: List of BacktestTrade objects or dicts

    Returns:
        ExecutionMetrics instance
    """
    # Convert objects to dicts for JSON storage
    equity_curve_dicts = [
        point.to_dict() if hasattr(point, "to_dict") else point for point in equity_curve
    ]
    trade_log_dicts = [
        trade.to_dict() if hasattr(trade, "to_dict") else trade for trade in trade_log
    ]

    # Downsample equity curve to prevent huge JSON payloads
    # (25 days of tick data can generate 1M+ points)
    if len(equity_curve_dicts) > MAX_EQUITY_CURVE_POINTS:
        logger.info(
            "Downsampling equity curve from %d to %d points",
            len(equity_curve_dicts),
            MAX_EQUITY_CURVE_POINTS,
        )
        equity_curve_dicts = _downsample_equity_curve(equity_curve_dicts, MAX_EQUITY_CURVE_POINTS)

    # Log sizes before creating metrics
    logger.info(
        "Creating ExecutionMetrics: equity_curve=%d points, trade_log=%d trades",
        len(equity_curve_dicts),
        len(trade_log_dicts),
    )

    return ExecutionMetrics.objects.create(
        execution=execution,
        total_return=Decimal(str(performance_metrics.get("total_return", 0))),
        total_pnl=Decimal(str(performance_metrics.get("total_pnl", 0))),
        total_trades=performance_metrics.get("total_trades", 0),
        winning_trades=performance_metrics.get("winning_trades", 0),
        losing_trades=performance_metrics.get("losing_trades", 0),
        win_rate=Decimal(str(performance_metrics.get("win_rate", 0))),
        max_drawdown=Decimal(str(performance_metrics.get("max_drawdown", 0))),
        sharpe_ratio=(
            Decimal(str(performance_metrics["sharpe_ratio"]))
            if performance_metrics.get("sharpe_ratio") is not None
            else None
        ),
        profit_factor=(
            Decimal(str(performance_metrics["profit_factor"]))
            if performance_metrics.get("profit_factor") is not None
            else None
        ),
        average_win=Decimal(str(performance_metrics.get("average_win", 0))),
        average_loss=Decimal(str(performance_metrics.get("average_loss", 0))),
        equity_curve=equity_curve_dicts,
        trade_log=trade_log_dicts,
        strategy_events=performance_metrics.get("strategy_events", []),
    )


@contextmanager
def task_execution_lock(
    task_type: str, task_id: int, timeout: int = LOCK_TIMEOUT
) -> Generator[bool, None, None]:
    """
    Context manager for task execution locking.

    Prevents concurrent execution of the same task using distributed locks (Redis).
    The lock is automatically released when the context exits.

    Args:
        task_type: Type of task ('backtest' or 'trading')
        task_id: ID of the task
        timeout: Lock timeout in seconds (default: 1 hour)

    Yields:
        bool: True if lock was acquired, False otherwise

    Requirements: 4.7, 4.9

    Example:
        with task_execution_lock('backtest', 123) as acquired:
            if not acquired:
                raise RuntimeError("Task is already running")
            # Execute task...
    """
    lock_key = f"{LOCK_KEY_PREFIX}{task_type}:{task_id}"
    lock_acquired = False

    try:
        # Try to acquire lock
        # cache.add() returns True if key was added (lock acquired)
        # Returns False if key already exists (lock held by another process)
        lock_acquired = cache.add(lock_key, "locked", timeout=timeout)

        if lock_acquired:
            logger.info(
                "Acquired execution lock for %s task %d",
                task_type,
                task_id,
            )
        else:
            logger.warning(
                "Failed to acquire execution lock for %s task %d - already running",
                task_type,
                task_id,
            )

        yield lock_acquired

    finally:
        # Release lock if we acquired it
        if lock_acquired:
            cache.delete(lock_key)
            logger.info(
                "Released execution lock for %s task %d",
                task_type,
                task_id,
            )


def is_task_locked(task_type: str, task_id: int) -> bool:
    """
    Check if a task execution lock is currently held.

    Args:
        task_type: Type of task ('backtest' or 'trading')
        task_id: ID of the task

    Returns:
        True if lock is held, False otherwise

    Requirements: 4.7, 4.9
    """
    lock_key = f"{LOCK_KEY_PREFIX}{task_type}:{task_id}"
    return cache.get(lock_key) is not None


# pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-nested-blocks,too-many-return-statements
# flake8: noqa: C901
def execute_backtest_task(
    task_id: int,
) -> dict[str, Any]:
    """
    Execute a backtest task with integrated progress tracking and state management.

    This function:
    1. Acquires execution lock using TaskLockManager
    2. Validates the task configuration
    3. Creates a TaskExecution record
    4. Initializes ProgressReporter, StateSynchronizer, and BacktestLogger
    5. Loads historical data day-by-day
    6. Runs the backtest engine with heartbeat updates
    7. Checks cancellation flag every iteration
    8. Reports progress after each day
    9. Creates ExecutionMetrics on completion
    10. Handles errors and updates status
    11. Releases execution lock

    Args:
        task_id: ID of the BacktestTask to execute

    Returns:
        Dictionary containing:
            - success: Whether execution completed successfully
            - task_id: BacktestTask ID
            - execution_id: TaskExecution ID
            - metrics: Performance metrics (if successful)
            - error: Error message (if failed)

    Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 4.1, 4.6, 4.7, 4.9, 5.2, 6.1, 6.2, 6.3,
        6.4, 7.1, 7.3, 7.4, 7.5
    """
    from trading.services.backtest_logger import BacktestLogger
    from trading.services.progress_reporter import ProgressReporter
    from trading.services.state_synchronizer import StateSynchronizer
    from trading.services.task_lock_manager import TaskLockManager

    execution = None
    task = None
    lock_manager = TaskLockManager()

    # Acquire execution lock using TaskLockManager
    if not lock_manager.acquire_lock("backtest", task_id):
        error_msg = "Task is already running. Cannot start concurrent execution."
        logger.error("Failed to acquire lock for backtest task %d", task_id)
        return {
            "success": False,
            "task_id": task_id,
            "execution_id": None,
            "error": error_msg,
        }

    try:
        # Fetch the task
        try:
            task = BacktestTask.objects.select_related("config", "user").get(id=task_id)
        except BacktestTask.DoesNotExist:
            error_msg = f"BacktestTask with id {task_id} does not exist"
            logger.error(error_msg)
            lock_manager.release_lock("backtest", task_id)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": error_msg,
            }

        # Validate configuration
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            logger.error("Task %d validation failed: %s", task_id, error_message)
            lock_manager.release_lock("backtest", task_id)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": f"Validation failed: {error_message}",
            }

        # Create TaskExecution record
        with transaction.atomic():
            # Get next execution number
            last_execution = (
                TaskExecution.objects.filter(
                    task_type=TaskType.BACKTEST,
                    task_id=task_id,
                )
                .order_by("-execution_number")
                .first()
            )
            execution_number = (last_execution.execution_number + 1) if last_execution else 1

            execution = TaskExecution.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task_id,
                execution_number=execution_number,
                status=TaskStatus.RUNNING,
                started_at=timezone.now(),
            )

            # Update task status
            task.status = TaskStatus.RUNNING
            task.save(update_fields=["status", "updated_at"])

        # Initialize services
        state_synchronizer = StateSynchronizer()
        backtest_logger = BacktestLogger(
            task_id=task.pk,
            execution_id=execution.pk,
            execution_number=execution.execution_number,
            user_id=task.user.pk,
        )

        # Calculate total days for progress tracking
        total_days = (task.end_time.date() - task.start_time.date()).days + 1
        progress_reporter = ProgressReporter(
            task_id=task.pk, execution_id=execution.pk, user_id=task.user.pk, total_days=total_days
        )

        logger.info(
            "Started backtest task %d execution #%d",
            task_id,
            execution_number,
        )

        # Use BacktestLogger for structured logging
        start_str = task.start_time.strftime("%Y-%m-%d %H:%M")
        end_str = task.end_time.strftime("%Y-%m-%d %H:%M")
        backtest_logger.log_execution_start(total_days, f"{start_str} to {end_str}")
        execution.add_log("INFO", f"Started backtest execution #{execution_number}")
        execution.add_log("INFO", f"Period: {start_str} to {end_str}")
        execution.add_log("INFO", f"Strategy: {task.config.strategy_type}")
        execution.add_log("INFO", f"Instrument: {task.instrument}")
        execution.add_log("INFO", f"Initial balance: ${task.initial_balance}")

        # Initialize data loader
        execution.add_log("INFO", f"Initializing data loader from {task.data_source}...")
        # Validate data_source is one of the expected literal values
        if task.data_source not in ("postgresql", "athena"):
            raise ValueError(f"Invalid data source: {task.data_source}")
        # Type narrowing: after validation, we know it's one of the literal values
        from typing import Literal, cast

        data_source = cast(Literal["postgresql", "athena"], task.data_source)
        data_loader = HistoricalDataLoader(data_source=data_source)

        execution.add_log("INFO", f"Processing {total_days} days of data incrementally...")

        # Get instrument from task (not from config parameters)
        instrument = task.instrument

        # Get resource limits and batch size from SystemSettings
        from accounts.models import SystemSettings

        try:
            sys_settings = SystemSettings.get_settings()
            cpu_limit = sys_settings.backtest_cpu_limit
            memory_limit = sys_settings.backtest_memory_limit
            day_batch_size = sys_settings.backtest_day_batch_size
        except Exception:  # pylint: disable=broad-exception-caught
            # Fallback to config file if SystemSettings not available
            cpu_limit = get_config("backtesting.cpu_limit", 1)
            memory_limit = get_config("backtesting.memory_limit", 2147483648)  # 2GB
            day_batch_size = 1  # Default to 1 day per batch

        # Create backtest configuration
        backtest_config = BacktestConfig(
            strategy_type=task.config.strategy_type,
            strategy_config=task.config.parameters,
            instrument=instrument,
            start_date=task.start_time,
            end_date=task.end_time,
            initial_balance=task.initial_balance,
            commission_per_trade=task.commission_per_trade,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
        )

        # Initialize backtest engine
        logger.info("Initializing backtest engine for task %d", task_id)
        execution.add_log("INFO", "Starting backtest engine...")
        execution.add_log(
            "INFO",
            f"CPU limit: {cpu_limit} cores, Memory limit: {memory_limit / (1024**3):.1f}GB",
        )
        engine = BacktestEngine(backtest_config)

        # Run incremental backtest with fetch-execute-notify cycle
        batch_msg = f"batch of {day_batch_size} day(s)" if day_batch_size > 1 else "day"
        execution.add_log(
            "INFO",
            f"Starting incremental backtest " f"(fetch → execute → notify per {batch_msg})...",
        )
        execution.add_log("INFO", f"Day batch size: {day_batch_size}")

        # Initialize strategy and monitoring
        # pylint: disable=protected-access
        engine._initialize_strategy()
        engine._start_resource_monitoring()
        engine._set_cpu_limit()
        # pylint: enable=protected-access

        # Process in batches: fetch N days → execute N days → notify
        current_date = task.start_time
        day_index = 0
        batch_tick_count = 0
        execution_start_time = timezone.now()
        last_strategy_event_index = 0  # Track logged strategy events to avoid duplicates

        while current_date.date() <= task.end_time.date():
            # Check cancellation flag at the start of each day
            if lock_manager.check_cancellation_flag("backtest", task_id):
                logger.info("Task %d cancelled by user", task_id)
                backtest_logger.log_warning("Task cancelled by user")
                execution.add_log("WARNING", "Task cancelled by user")

                # Stop resource monitoring
                if engine.resource_monitor:
                    engine.resource_monitor.stop()

                # Transition to stopped state
                state_synchronizer.transition_to_stopped(task, execution)

                # Release lock
                lock_manager.release_lock("backtest", task_id)

                return {
                    "success": False,
                    "task_id": task_id,
                    "execution_id": execution.pk,
                    "error": "Task cancelled by user",
                }

            # Update heartbeat
            lock_manager.update_heartbeat("backtest", task_id)

            # Report day start
            progress_reporter.report_day_start(current_date, day_index)
            backtest_logger.log_day_start(day_index, total_days, current_date.strftime("%Y-%m-%d"))

            # STEP 1: Fetch data for this day
            execution.add_log("INFO", f"Fetching data for {current_date.strftime('%Y-%m-%d')}...")
            day_tick_data, load_error = _load_backtest_data_by_day(task, data_loader, current_date)

            if load_error:
                logger.error(load_error)
                backtest_logger.log_error(load_error)
                execution.add_log("ERROR", load_error)
                if engine.resource_monitor:
                    engine.resource_monitor.stop()

                # Transition to failed state
                state_synchronizer.transition_to_failed(task, execution, load_error)

                # Release lock
                lock_manager.release_lock("backtest", task_id)

                return {
                    "success": False,
                    "task_id": task_id,
                    "execution_id": execution.pk,
                    "error": load_error,
                }

            # STEP 2: Execute backtest for this day
            day_start_time = timezone.now()
            if day_tick_data:
                date_str = current_date.strftime("%Y-%m-%d")
                backtest_logger.log_day_processing(day_index, total_days, len(day_tick_data))
                execution.add_log(
                    "INFO",
                    f"Processing {len(day_tick_data)} ticks for {date_str}...",
                )
                batch_tick_count += len(day_tick_data)

                # Record initial equity on the first day using first tick timestamp
                # pylint: disable=protected-access
                if day_index == 0:
                    engine._record_equity(day_tick_data[0].timestamp)
                # pylint: enable=protected-access

                # For large tick batches (>100k), report intermediate progress
                tick_count = len(day_tick_data)
                report_interval = 10000 if tick_count > 100000 else tick_count + 1

                for tick_idx, tick in enumerate(day_tick_data):
                    # Check cancellation flag periodically during large batches
                    if tick_idx % 10000 == 0 and lock_manager.check_cancellation_flag(
                        "backtest", task_id
                    ):
                        logger.info("Task %d cancelled by user during tick processing", task_id)
                        backtest_logger.log_warning("Task cancelled by user during tick processing")
                        execution.add_log("WARNING", "Task cancelled by user")

                        if engine.resource_monitor:
                            engine.resource_monitor.stop()

                        state_synchronizer.transition_to_stopped(task, execution)
                        lock_manager.release_lock("backtest", task_id)

                        return {
                            "success": False,
                            "task_id": task_id,
                            "execution_id": execution.pk,
                            "error": "Task cancelled by user",
                        }

                    # Check resource limits
                    if engine.resource_monitor and engine.resource_monitor.is_exceeded():
                        engine.terminated = True
                        memory_mb = engine.config.memory_limit / 1024 / 1024
                        error_msg = f"Memory limit exceeded ({memory_mb:.0f}MB)"
                        backtest_logger.log_error(error_msg)
                        execution.add_log("ERROR", error_msg)
                        if engine.resource_monitor:
                            engine.resource_monitor.stop()
                        raise RuntimeError(error_msg)

                    # Process tick
                    engine._process_tick(tick)  # pylint: disable=protected-access

                    # Report intermediate progress for large batches
                    if tick_idx > 0 and tick_idx % report_interval == 0:
                        elapsed = (timezone.now() - day_start_time).total_seconds()
                        progress_reporter.report_day_progress(tick_idx, tick_count)
                        backtest_logger.log_tick_progress(
                            tick_idx, tick_count, elapsed, day_index, total_days
                        )

                # Record equity at end of day
                # pylint: disable=protected-access
                engine._record_equity(day_tick_data[-1].timestamp)

            # Calculate day processing time
            day_processing_time = (timezone.now() - day_start_time).total_seconds()

            # Report day complete
            progress_reporter.report_day_complete(day_index, day_processing_time)
            backtest_logger.log_day_complete(day_index, total_days, day_processing_time)

            # Log floor strategy events to execution logs
            last_strategy_event_index = _log_strategy_events_to_execution(
                execution, engine, last_strategy_event_index
            )

            # Clear day tick data to free memory (data is no longer needed)
            del day_tick_data
            day_tick_data = []

            # Move to next day
            day_index += 1
            current_date += timedelta(days=1)

            # STEP 3: Send notification after batch is complete or at end
            should_notify = (day_index % day_batch_size == 0) or (
                current_date.date() > task.end_time.date()
            )

            if should_notify:
                # Calculate intermediate metrics and notify
                intermediate_metrics = engine.calculate_performance_metrics()
                progress = int((day_index / total_days) * 100)

                # Prepare full trade log for live display
                all_trades = [t.to_dict() for t in engine.trade_log] if engine.trade_log else []

                # Get strategy events for live display (floor layer markers, etc.)
                strategy_events = []
                if engine.strategy and hasattr(engine.strategy, "_backtest_events"):
                    # pylint: disable=protected-access
                    strategy_events = engine.strategy._backtest_events

                # Get equity curve for live display (last 100 points for Overview tab)
                equity_points = (
                    [p.to_dict() for p in engine.equity_curve[-100:]] if engine.equity_curve else []
                )

                # Use the last processed date for the batch
                batch_end_date = (current_date - timedelta(days=1)).date()

                intermediate_results = {
                    "day_date": batch_end_date.isoformat(),
                    "progress": progress,
                    "days_processed": day_index,
                    "total_days": total_days,
                    "ticks_processed": batch_tick_count,
                    "balance": float(engine.balance),
                    "total_trades": len(engine.trade_log),
                    "metrics": intermediate_metrics,
                    "trade_log": all_trades,
                    "strategy_events": strategy_events,
                    "equity_curve": equity_points,
                }

                # Update progress via execution model
                execution.update_progress(progress, user_id=task.user.pk)

                # Log progress
                execution.add_log(
                    "INFO",
                    f"Day {day_index}/{total_days}: "
                    f"{batch_end_date.isoformat()} - "
                    f"Balance: ${intermediate_results['balance']:,.2f}, "
                    f"Trades: {intermediate_results['total_trades']}",
                )

                # Send intermediate results via WebSocket
                from trading.services.notifications import send_backtest_intermediate_results

                try:
                    send_backtest_intermediate_results(
                        task_id=task_id,
                        execution_id=execution.pk,
                        user_id=task.user.pk,
                        intermediate_results=intermediate_results,
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("Failed to send intermediate results: %s", e)

                # Reset batch tick counter
                batch_tick_count = 0

        # Finalize strategy to save final state
        if engine.strategy and hasattr(engine.strategy, "finalize"):
            try:
                engine.strategy.finalize()
                execution.add_log("INFO", "Strategy state finalized")
            except Exception as e:
                logger.warning("Failed to finalize strategy: %s", e)

        # Stop resource monitoring
        if engine.resource_monitor:
            engine.resource_monitor.stop()
            engine._log_resource_usage()  # pylint: disable=protected-access

        # Get final results
        trade_log = engine.trade_log
        equity_curve = engine.equity_curve
        performance_metrics = engine.calculate_performance_metrics()

        # Calculate total execution time
        total_execution_time = (timezone.now() - execution_start_time).total_seconds()

        # Log execution complete
        backtest_logger.log_execution_complete(total_execution_time, len(trade_log))

        execution.add_log(
            "INFO",
            f"Incremental backtest completed: {len(trade_log)} trades, "
            f"final balance: {engine.balance}",
        )

        execution.add_log("INFO", "=" * 60)
        execution.add_log("INFO", "BACKTEST EXECUTION COMPLETED")
        execution.add_log("INFO", "=" * 60)

        # Initial state
        execution.add_log("INFO", "")
        execution.add_log("INFO", "INITIAL STATE:")
        execution.add_log("INFO", f"  Initial Balance: ${task.initial_balance:,.2f}")
        execution.add_log("INFO", f"  Commission per Trade: ${task.commission_per_trade}")

        # Final state
        execution.add_log("INFO", "")
        execution.add_log("INFO", "FINAL STATE:")
        execution.add_log("INFO", f"  Final Balance: ${engine.balance:,.2f}")
        execution.add_log(
            "INFO", f"  Total Return: {performance_metrics.get('total_return', 0):.2f}%"
        )
        execution.add_log("INFO", f"  Total P&L: ${performance_metrics.get('total_pnl', 0):,.2f}")

        # Trading statistics
        execution.add_log("INFO", "")
        execution.add_log("INFO", "TRADING STATISTICS:")
        execution.add_log("INFO", f"  Total Trades: {len(trade_log)}")
        execution.add_log(
            "INFO", f"  Winning Trades: {performance_metrics.get('winning_trades', 0)}"
        )
        execution.add_log("INFO", f"  Losing Trades: {performance_metrics.get('losing_trades', 0)}")
        execution.add_log("INFO", f"  Win Rate: {performance_metrics.get('win_rate', 0):.2f}%")

        # Performance metrics
        execution.add_log("INFO", "")
        execution.add_log("INFO", "PERFORMANCE METRICS:")
        execution.add_log(
            "INFO", f"  Max Drawdown: {performance_metrics.get('max_drawdown', 0):.2f}%"
        )
        execution.add_log(
            "INFO", f"  Average Win: ${performance_metrics.get('average_win', 0):,.2f}"
        )
        execution.add_log(
            "INFO", f"  Average Loss: ${performance_metrics.get('average_loss', 0):,.2f}"
        )
        if performance_metrics.get("sharpe_ratio") is not None:
            execution.add_log(
                "INFO", f"  Sharpe Ratio: {performance_metrics.get('sharpe_ratio'):.3f}"
            )
        if performance_metrics.get("profit_factor") is not None:
            execution.add_log(
                "INFO", f"  Profit Factor: {performance_metrics.get('profit_factor'):.3f}"
            )

        # Trade details
        if len(trade_log) > 0:
            execution.add_log("INFO", "")
            execution.add_log("INFO", "TRADE LOG:")
            execution.add_log("INFO", "-" * 60)
            for i, trade in enumerate(trade_log[:10], 1):  # Show first 10 trades
                execution.add_log("INFO", f"Trade #{i}:")
                execution.add_log("INFO", f"  Direction: {trade.direction}")
                execution.add_log("INFO", f"  Instrument: {trade.instrument}")
                execution.add_log("INFO", f"  Units: {trade.units}")
                execution.add_log("INFO", f"  Entry Price: {trade.entry_price:.5f}")
                execution.add_log("INFO", f"  Exit Price: {trade.exit_price:.5f}")
                pnl_sign = "+" if trade.pnl >= 0 else ""
                execution.add_log("INFO", f"  P&L: {pnl_sign}${trade.pnl:,.2f}")
                execution.add_log("INFO", f"  Entry Time: {trade.entry_time.isoformat()}")
                execution.add_log("INFO", f"  Exit Time: {trade.exit_time.isoformat()}")
                execution.add_log("INFO", "")

            if len(trade_log) > 10:
                execution.add_log("INFO", f"... and {len(trade_log) - 10} more trades")
                execution.add_log("INFO", "")

        execution.add_log("INFO", "=" * 60)

        logger.info(
            "Backtest completed: %d trades, final balance: %s",
            len(trade_log),
            engine.balance,
        )

        # IMPORTANT: Update status to COMPLETED first, BEFORE creating metrics
        # This ensures that if the process is killed during metrics creation (OOM),
        # the task is still marked as completed.
        state_synchronizer.transition_to_completed(task, execution)

        logger.info(
            "Backtest task %d execution #%d marked as COMPLETED",
            task_id,
            execution_number,
        )

        # Create ExecutionMetrics (this can be memory-intensive with large equity curves)
        # If this fails, the task is still marked as completed
        metrics = None
        logger.info("Starting ExecutionMetrics creation for execution %d...", execution.pk)
        try:
            with transaction.atomic():
                metrics = _create_execution_metrics(
                    execution, performance_metrics, equity_curve, trade_log
                )
            logger.info("ExecutionMetrics created for execution %d", execution.pk)
        except Exception as metrics_error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to create ExecutionMetrics for execution %d: %s",
                execution.pk,
                metrics_error,
                exc_info=True,
            )
            try:
                execution.add_log("WARNING", f"Failed to save detailed metrics: {metrics_error}")
            except Exception as log_error:  # pylint: disable=broad-exception-caught  # nosec B110
                # Log the failure but don't let it prevent task completion
                logger.warning(
                    "Failed to add log entry for execution %d: %s",
                    execution.pk,
                    log_error,
                )
        logger.info("ExecutionMetrics creation attempt completed for execution %d", execution.pk)

        # Release lock
        lock_manager.release_lock("backtest", task_id)

        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution.pk,
            "metrics": metrics.get_trade_summary() if metrics else None,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Backtest execution failed: {str(e)}"
        logger.error(
            "Error executing backtest task %d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )

        # Mark execution as failed
        if execution:
            backtest_logger.log_error(f"Execution failed: {str(e)}")
            execution.add_log("ERROR", f"Execution failed: {str(e)}")

            # Use StateSynchronizer to transition to failed state
            if task:
                state_synchronizer.transition_to_failed(task, execution, error_msg)

        # Release lock
        lock_manager.release_lock("backtest", task_id)

        return {
            "success": False,
            "task_id": task_id,
            "execution_id": execution.pk if execution else None,
            "error": error_msg,
        }


# pylint: disable=too-many-return-statements,too-many-statements
def execute_trading_task(
    task_id: int,
) -> dict[str, Any]:
    """
    Execute a trading task.

    This function:
    1. Acquires execution lock to prevent concurrent execution
    2. Validates the task configuration
    3. Creates a TaskExecution record
    4. Initializes the strategy executor
    5. Starts market data streaming
    6. Handles pause/resume logic
    7. Creates ExecutionMetrics periodically
    8. Handles errors and updates status

    Note: This function starts the execution but returns immediately.
    The actual trading runs in the background via market data streaming.
    The lock is held for the duration of the trading session.

    Args:
        task_id: ID of the TradingTask to execute

    Returns:
        Dictionary containing:
            - success: Whether execution started successfully
            - task_id: TradingTask ID
            - execution_id: TaskExecution ID
            - error: Error message (if failed)

    Requirements: 4.2, 4.3, 4.4, 4.5, 4.7, 4.9, 7.2, 7.3
    """
    execution = None
    task = None

    # Check if task is already locked (running)
    if is_task_locked("trading", task_id):
        error_msg = "Task is already running. Cannot start concurrent execution."
        logger.error("Task %d is already locked", task_id)
        return {
            "success": False,
            "task_id": task_id,
            "execution_id": None,
            "error": error_msg,
        }

    # Acquire lock (will be held until task is stopped)
    lock_key = f"{LOCK_KEY_PREFIX}trading:{task_id}"
    lock_acquired = cache.add(lock_key, "locked", timeout=LOCK_TIMEOUT)

    if not lock_acquired:
        error_msg = "Failed to acquire execution lock. Task may already be running."
        logger.error("Failed to acquire lock for trading task %d", task_id)
        return {
            "success": False,
            "task_id": task_id,
            "execution_id": None,
            "error": error_msg,
        }

    logger.info("Acquired execution lock for trading task %d", task_id)

    try:
        # Fetch the task
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id
            )
        except TradingTask.DoesNotExist:
            error_msg = f"TradingTask with id {task_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": error_msg,
            }

        # Validate configuration
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            logger.error("Task %d validation failed: %s", task_id, error_message)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": f"Validation failed: {error_message}",
            }

        # Check if another task is running on this account
        other_running_tasks = TradingTask.objects.filter(
            oanda_account=task.oanda_account,
            status=TaskStatus.RUNNING,
        ).exclude(id=task_id)

        if other_running_tasks.exists():
            other_task = other_running_tasks.first()
            if other_task:
                error_msg = (
                    f"Another task '{other_task.name}' is already running on this account. "
                    "Only one task can run per account at a time."
                )
            else:
                error_msg = (
                    "Another task is already running on this account. "
                    "Only one task can run per account at a time."
                )
            logger.error(error_msg)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": error_msg,
            }

        # Create TaskExecution record
        with transaction.atomic():
            # Get next execution number
            last_execution = (
                TaskExecution.objects.filter(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                )
                .order_by("-execution_number")
                .first()
            )
            execution_number = (last_execution.execution_number + 1) if last_execution else 1

            execution = TaskExecution.objects.create(
                task_type=TaskType.TRADING,
                task_id=task_id,
                execution_number=execution_number,
                status=TaskStatus.RUNNING,
                started_at=timezone.now(),
            )

            # Update task status
            task.status = TaskStatus.RUNNING
            task.save(update_fields=["status", "updated_at"])

        logger.info(
            "Started trading task %d execution #%d on account %s",
            task_id,
            execution_number,
            task.oanda_account.account_id,
        )

        execution.add_log("INFO", f"Started trading execution #{execution_number}")
        execution.add_log("INFO", f"Strategy: {task.config.strategy_type}")
        execution.add_log("INFO", f"Account: {task.oanda_account.account_id}")
        execution.add_log("INFO", f"Account type: {task.oanda_account.api_type}")

        # Initialize strategy executor
        # Note: The actual strategy execution happens via market data streaming
        # which is managed by the start_market_data_stream Celery task

        # Get instrument from configuration
        instrument = task.config.parameters.get("instrument", [])

        if not instrument:
            error_msg = "No instrument specified in configuration"
            logger.error(error_msg)
            execution.add_log("ERROR", error_msg)
            execution.mark_failed(ValueError(error_msg))
            task.status = TaskStatus.FAILED
            task.save(update_fields=["status", "updated_at"])
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": execution.pk,
                "error": error_msg,
            }

        execution.add_log("INFO", f"Instrument: {instrument}")

        # Start market data streaming for the account
        # This will be handled by the Celery task in the next subtask
        logger.info(
            "Trading task %d execution #%d started successfully. "
            "Market data streaming should be started separately.",
            task_id,
            execution_number,
        )

        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution.pk,
            "account_id": task.oanda_account.account_id,
            "instrument": instrument,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Trading task execution failed: {str(e)}"
        logger.error(
            "Error executing trading task %d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )

        # Mark execution as failed
        if execution:
            execution.mark_failed(e)

        # Update task status
        if task:
            task.status = TaskStatus.FAILED
            task.save(update_fields=["status", "updated_at"])

        return {
            "success": False,
            "task_id": task_id,
            "execution_id": execution.pk if execution else None,
            "error": error_msg,
        }


def _close_all_positions_for_trading_task(task: TradingTask) -> int:
    """
    Close all open positions for a trading task at current market price.

    This helper method generates close orders for all open positions
    and executes them at the current market price from the latest tick data.

    Args:
        task: TradingTask instance

    Returns:
        Number of positions closed

    Requirements: 10.2, 10.4
    """
    from trading.models import Order, Position, Strategy
    from trading.order_executor import OrderExecutor
    from trading.tick_data_models import TickData

    closed_count = 0

    try:
        # Get the strategy instance for this task
        try:
            strategy = Strategy.objects.get(
                account=task.oanda_account,
                strategy_type=task.config.strategy_type,
                is_active=True,
            )
        except Strategy.DoesNotExist:
            logger.warning(
                "No active strategy found for task %d, cannot close positions",
                task.pk,
            )
            return 0

        # Get all open positions for this strategy
        open_positions = Position.objects.filter(
            account=task.oanda_account,
            strategy=strategy,
            closed_at__isnull=True,
        )

        if not open_positions.exists():
            logger.info("No open positions to close for task %d", task.pk)
            return 0

        logger.info(
            "Found %d open positions to close for task %d",
            open_positions.count(),
            task.pk,
        )

        # Get the instrument from the task configuration
        instrument = task.config.parameters.get("instrument")
        if not instrument:
            logger.error("No instrument found in task configuration")
            return 0

        # Get the latest tick data for this instrument
        latest_tick = (
            TickData.objects.filter(
                instrument=instrument,
            )
            .order_by("-timestamp")
            .first()
        )

        if not latest_tick:
            # If no tick data exists, use the position's current price as fallback
            logger.warning(
                "No tick data found for instrument %s, using position current prices",
                instrument,
            )

        # Create close orders for each position
        order_executor = OrderExecutor(task.oanda_account)

        for position in open_positions:
            try:
                # Determine exit price based on position direction
                # For long positions, we sell at bid price
                # For short positions, we buy at ask price
                if latest_tick:
                    if position.direction == "long":
                        exit_price = latest_tick.bid
                    else:
                        exit_price = latest_tick.ask
                else:
                    # Fallback to current price if no tick data
                    exit_price = position.current_price

                # Create close order
                close_order = Order.objects.create(
                    account=task.oanda_account,
                    strategy=strategy,
                    instrument=position.instrument,
                    direction="sell" if position.direction == "long" else "buy",
                    units=position.units,
                    order_type="market",
                    status="pending",
                    order_id=f"CLOSE-{position.pk}-{timezone.now().timestamp()}",
                )

                # Execute the close order
                order_executor.execute_order(close_order)  # type: ignore[attr-defined]

                # Close the position using the close() method
                realized_pnl = position.close(exit_price)

                closed_count += 1

                logger.info(
                    "Closed position %d: %s %s %s at %s (P&L: %s)",
                    position.pk,
                    position.direction,
                    position.units,
                    position.instrument,
                    exit_price,
                    realized_pnl,
                )

                # Log close event to strategy if it has the method
                try:
                    strategy_class = registry.get_strategy_class(strategy.strategy_type)
                    strategy_instance = strategy_class(strategy)

                    if hasattr(strategy_instance, "log_strategy_event"):
                        strategy_instance.log_strategy_event(
                            "position_closed",
                            f"Position closed at task stop: {position.direction} "
                            f"{position.units} {position.instrument}",
                            {
                                "instrument": position.instrument,
                                "direction": position.direction,
                                "units": str(position.units),
                                "entry_price": str(position.entry_price),
                                "exit_price": str(exit_price),
                                "pnl": str(realized_pnl),
                                "event_type": "close",
                                "reason": "task_stop",
                            },
                        )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to log close event for position %d: %s",
                        position.pk,
                        str(e),
                    )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to close position %d: %s",
                    position.pk,
                    str(e),
                    exc_info=True,
                )
                # Continue closing other positions

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "Error closing positions for task %d: %s",
            task.pk,
            str(e),
            exc_info=True,
        )

    return closed_count


def stop_trading_task_execution(task_id: int) -> dict[str, Any]:
    """
    Stop a running trading task execution.

    This function:
    1. Finds the current execution
    2. Closes all positions if sell_on_stop is enabled
    3. Stops market data streaming
    4. Calculates final metrics
    5. Marks execution as stopped
    6. Releases execution lock

    Args:
        task_id: ID of the TradingTask to stop

    Returns:
        Dictionary containing:
            - success: Whether stop was successful
            - task_id: TradingTask ID
            - execution_id: TaskExecution ID
            - error: Error message (if failed)

    Requirements: 4.3, 4.7, 4.9, 7.2, 7.3, 10.2, 10.4
    """
    try:
        # Fetch the task
        try:
            task = TradingTask.objects.select_related("config", "oanda_account").get(id=task_id)
        except TradingTask.DoesNotExist:
            error_msg = f"TradingTask with id {task_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": None,
                "error": error_msg,
            }

        # Get current execution
        execution = task.get_latest_execution()
        if not execution or execution.status != TaskStatus.RUNNING:
            error_msg = "No running execution found for this task"
            logger.error(error_msg)
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": execution.pk if execution else None,
                "error": error_msg,
            }

        # Close all positions if sell_on_stop is enabled
        if task.sell_on_stop:
            logger.info(
                "Closing all positions for task %d (sell_on_stop=True)",
                task_id,
            )
            try:
                closed_count = _close_all_positions_for_trading_task(task)
                logger.info(
                    "Closed %d positions for task %d at task stop",
                    closed_count,
                    task_id,
                )
                execution.add_log(
                    "INFO",
                    f"Closed {closed_count} positions at task stop (sell_on_stop=True)",
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error closing positions for task %d: %s",
                    task_id,
                    str(e),
                    exc_info=True,
                )
                execution.add_log(
                    "ERROR",
                    f"Failed to close positions at task stop: {str(e)}",
                )
        else:
            logger.info(
                "Preserving open positions for task %d (sell_on_stop=False)",
                task_id,
            )

        # Stop market data streaming
        # This will be handled by the stop_market_data_stream Celery task

        # Mark execution as stopped
        execution.status = TaskStatus.STOPPED
        execution.completed_at = timezone.now()
        execution.save(update_fields=["status", "completed_at"])

        # Update task status
        task.status = TaskStatus.STOPPED
        task.save(update_fields=["status", "updated_at"])

        # Release execution lock
        lock_key = f"{LOCK_KEY_PREFIX}trading:{task_id}"
        cache.delete(lock_key)
        logger.info("Released execution lock for trading task %d", task_id)

        logger.info(
            "Stopped trading task %d execution #%d",
            task_id,
            execution.execution_number,
        )

        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution.pk,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to stop trading task: {str(e)}"
        logger.error(
            "Error stopping trading task %d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "task_id": task_id,
            "execution_id": None,
            "error": error_msg,
        }


def pause_trading_task_execution(task_id: int) -> dict[str, Any]:
    """
    Pause a running trading task execution.

    Args:
        task_id: ID of the TradingTask to pause

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.4, 7.3
    """
    try:
        task = TradingTask.objects.get(id=task_id)
        execution = task.get_latest_execution()

        if not execution or execution.status != TaskStatus.RUNNING:
            return {
                "success": False,
                "task_id": task_id,
                "error": "No running execution found",
            }

        execution.status = TaskStatus.PAUSED
        execution.save(update_fields=["status"])

        task.status = TaskStatus.PAUSED
        task.save(update_fields=["status", "updated_at"])

        logger.info("Paused trading task %d execution #%d", task_id, execution.execution_number)

        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution.pk,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to pause trading task: {str(e)}"
        logger.error("Error pausing trading task %d: %s", task_id, error_msg, exc_info=True)
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }


def resume_trading_task_execution(task_id: int) -> dict[str, Any]:
    """
    Resume a paused trading task execution.

    Args:
        task_id: ID of the TradingTask to resume

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.4, 7.3
    """
    try:
        task = TradingTask.objects.get(id=task_id)
        execution = task.get_latest_execution()

        if not execution or execution.status != TaskStatus.PAUSED:
            return {
                "success": False,
                "task_id": task_id,
                "error": "No paused execution found",
            }

        execution.status = TaskStatus.RUNNING
        execution.save(update_fields=["status"])

        task.status = TaskStatus.RUNNING
        task.save(update_fields=["status", "updated_at"])

        logger.info("Resumed trading task %d execution #%d", task_id, execution.execution_number)

        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution.pk,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to resume trading task: {str(e)}"
        logger.error("Error resuming trading task %d: %s", task_id, error_msg, exc_info=True)
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }
