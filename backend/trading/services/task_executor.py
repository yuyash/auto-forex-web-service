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
from trading.services.notifications import send_task_status_notification
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


# pylint: disable=too-many-locals,too-many-statements,too-many-branches
# flake8: noqa: C901
def execute_backtest_task(
    task_id: int,
) -> dict[str, Any]:
    """
    Execute a backtest task.

    This function:
    1. Acquires execution lock to prevent concurrent execution
    2. Validates the task configuration
    3. Creates a TaskExecution record
    4. Loads historical data
    5. Runs the backtest engine
    6. Creates ExecutionMetrics on completion
    7. Handles errors and updates status
    8. Releases execution lock

    Args:
        task_id: ID of the BacktestTask to execute

    Returns:
        Dictionary containing:
            - success: Whether execution completed successfully
            - task_id: BacktestTask ID
            - execution_id: TaskExecution ID
            - metrics: Performance metrics (if successful)
            - error: Error message (if failed)

    Requirements: 4.1, 4.6, 4.7, 4.9, 7.1, 7.3, 7.4, 7.5
    """
    execution = None
    task = None

    # Acquire execution lock
    with task_execution_lock("backtest", task_id) as lock_acquired:
        if not lock_acquired:
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

            logger.info(
                "Started backtest task %d execution #%d",
                task_id,
                execution_number,
            )
            execution.add_log("INFO", f"Started backtest execution #{execution_number}")
            start_str = task.start_time.strftime("%Y-%m-%d %H:%M")
            end_str = task.end_time.strftime("%Y-%m-%d %H:%M")
            execution.add_log("INFO", f"Period: {start_str} to {end_str}")
            execution.add_log("INFO", f"Strategy: {task.config.strategy_type}")
            execution.add_log("INFO", f"Instrument: {task.instrument}")
            execution.add_log("INFO", f"Initial balance: {task.initial_balance}")

            # Initialize data loader
            execution.add_log("INFO", f"Initializing data loader from {task.data_source}...")
            # Validate data_source is one of the expected literal values
            if task.data_source not in ("postgresql", "athena"):
                raise ValueError(f"Invalid data source: {task.data_source}")
            # Type narrowing: after validation, we know it's one of the literal values
            from typing import Literal, cast

            data_source = cast(Literal["postgresql", "athena"], task.data_source)
            data_loader = HistoricalDataLoader(data_source=data_source)

            # Calculate total days for progress tracking
            total_days = (task.end_time.date() - task.start_time.date()).days + 1
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

            # Define callback for day completion with intermediate results
            # pylint: disable=unused-argument
            def day_complete_callback(day_date: Any, intermediate_results: dict[str, Any]) -> None:
                """Send intermediate backtest results via WebSocket after each day."""
                try:
                    # Update progress
                    progress = intermediate_results["progress"]
                    execution.update_progress(progress, user_id=task.user.id)

                    # Log progress
                    execution.add_log(
                        "INFO",
                        f"Day {intermediate_results['days_processed']}/{intermediate_days}: "
                        f"{intermediate_results['day_date']} - "
                        f"Balance: ${intermediate_results['balance']:,.2f}, "
                        f"Trades: {intermediate_results['total_trades']}",
                    )

                    # Send intermediate results via WebSocket
                    from trading.services.notifications import send_backtest_intermediate_results

                    send_backtest_intermediate_results(
                        task_id=task_id,
                        execution_id=execution.id,
                        user_id=task.user.id,
                        intermediate_results=intermediate_results,
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("Failed to send intermediate results: %s", e)

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
            intermediate_days = total_days
            batch_tick_count = 0

            while current_date.date() <= task.end_time.date():
                # STEP 1: Fetch data for this day
                execution.add_log(
                    "INFO", f"Fetching data for {current_date.strftime('%Y-%m-%d')}..."
                )
                day_tick_data, load_error = _load_backtest_data_by_day(
                    task, data_loader, current_date
                )

                if load_error:
                    logger.error(load_error)
                    execution.add_log("ERROR", load_error)
                    if engine.resource_monitor:
                        engine.resource_monitor.stop()
                    execution.mark_failed(RuntimeError(load_error))
                    task.status = TaskStatus.FAILED
                    task.save(update_fields=["status", "updated_at"])
                    return {
                        "success": False,
                        "task_id": task_id,
                        "execution_id": execution.id,
                        "error": load_error,
                    }

                # STEP 2: Execute backtest for this day
                if day_tick_data:
                    date_str = current_date.strftime("%Y-%m-%d")
                    execution.add_log(
                        "INFO",
                        f"Processing {len(day_tick_data)} ticks for {date_str}...",
                    )
                    batch_tick_count += len(day_tick_data)

                    for tick in day_tick_data:
                        # Check resource limits
                        if engine.resource_monitor and engine.resource_monitor.is_exceeded():
                            engine.terminated = True
                            memory_mb = engine.config.memory_limit / 1024 / 1024
                            error_msg = f"Memory limit exceeded ({memory_mb:.0f}MB)"
                            execution.add_log("ERROR", error_msg)
                            if engine.resource_monitor:
                                engine.resource_monitor.stop()
                            raise RuntimeError(error_msg)

                        # Process tick
                        engine._process_tick(tick)  # pylint: disable=protected-access

                    # Record equity at end of day
                    # pylint: disable=protected-access
                    engine._record_equity(day_tick_data[-1].timestamp)

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

                    # Prepare intermediate results
                    recent_trades = (
                        [t.to_dict() for t in engine.trade_log[-10:]] if engine.trade_log else []
                    )
                    equity_points = (
                        [p.to_dict() for p in engine.equity_curve[-100:]]
                        if engine.equity_curve
                        else []
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
                        "recent_trades": recent_trades,
                        "equity_curve": equity_points,
                    }

                    # Send notification
                    day_complete_callback(batch_end_date, intermediate_results)

                    # Reset batch tick counter
                    batch_tick_count = 0

            # Stop resource monitoring
            if engine.resource_monitor:
                engine.resource_monitor.stop()
                engine._log_resource_usage()  # pylint: disable=protected-access

            # Get final results
            trade_log = engine.trade_log
            equity_curve = engine.equity_curve
            performance_metrics = engine.calculate_performance_metrics()

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
            execution.add_log(
                "INFO", f"  Total P&L: ${performance_metrics.get('total_pnl', 0):,.2f}"
            )

            # Trading statistics
            execution.add_log("INFO", "")
            execution.add_log("INFO", "TRADING STATISTICS:")
            execution.add_log("INFO", f"  Total Trades: {len(trade_log)}")
            execution.add_log(
                "INFO", f"  Winning Trades: {performance_metrics.get('winning_trades', 0)}"
            )
            execution.add_log(
                "INFO", f"  Losing Trades: {performance_metrics.get('losing_trades', 0)}"
            )
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

            # Create ExecutionMetrics
            with transaction.atomic():
                metrics = _create_execution_metrics(
                    execution, performance_metrics, equity_curve, trade_log
                )

                # Mark execution as completed
                execution.mark_completed()

                # Update task status
                task.status = TaskStatus.COMPLETED
                task.save(update_fields=["status", "updated_at"])

                # Send WebSocket notification
                send_task_status_notification(
                    user_id=task.user.id,
                    task_id=task.id,
                    task_name=task.name,
                    task_type="backtest",
                    status=TaskStatus.COMPLETED,
                    execution_id=execution.id,
                )

            logger.info(
                "Backtest task %d execution #%d completed successfully",
                task_id,
                execution_number,
            )

            return {
                "success": True,
                "task_id": task_id,
                "execution_id": execution.id,
                "metrics": metrics.get_trade_summary(),
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
                execution.add_log("ERROR", f"Execution failed: {str(e)}")
                execution.mark_failed(e)

            # Update task status
            if task:
                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])

                # Send WebSocket notification
                send_task_status_notification(
                    user_id=task.user.id,
                    task_id=task.id,
                    task_name=task.name,
                    task_type="backtest",
                    status=TaskStatus.FAILED,
                    execution_id=execution.id if execution else None,
                    error_message=error_msg,
                )

            return {
                "success": False,
                "task_id": task_id,
                "execution_id": execution.id if execution else None,
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
                "execution_id": execution.id,
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
            "execution_id": execution.id,
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
            "execution_id": execution.id if execution else None,
            "error": error_msg,
        }


def stop_trading_task_execution(task_id: int) -> dict[str, Any]:
    """
    Stop a running trading task execution.

    This function:
    1. Finds the current execution
    2. Stops market data streaming
    3. Calculates final metrics
    4. Marks execution as stopped
    5. Releases execution lock

    Args:
        task_id: ID of the TradingTask to stop

    Returns:
        Dictionary containing:
            - success: Whether stop was successful
            - task_id: TradingTask ID
            - execution_id: TaskExecution ID
            - error: Error message (if failed)

    Requirements: 4.3, 4.7, 4.9, 7.2, 7.3
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
                "execution_id": execution.id if execution else None,
                "error": error_msg,
            }

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
            "execution_id": execution.id,
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
            "execution_id": execution.id,
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
            "execution_id": execution.id,
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
