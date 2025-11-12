"""
Task execution service for backtest and trading tasks.

This module provides functions for executing backtest and trading tasks,
handling TaskExecution creation, status updates, and ExecutionMetrics generation.

Requirements: 4.1, 4.2, 4.3, 4.6, 4.8, 7.3, 7.4, 7.5, 4.7, 4.9
"""

import logging
from contextlib import contextmanager
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
        task.config.parameters.get("instrument", []),
        task.start_time,
        task.end_time,
    )

    tick_data = []
    instrument = task.config.parameters.get("instrument", [])

    # FIXME: Changed from loop - for instrument in instrument:
    instrument_data = data_loader.load_data(
        instrument=instrument,
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
        equity_curve: Equity curve data
        trade_log: Trade log data

    Returns:
        ExecutionMetrics instance
    """
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
        equity_curve=equity_curve,
        trade_log=trade_log,
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


# pylint: disable=too-many-locals,too-many-statements
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

            # Load historical data
            data_loader = HistoricalDataLoader()
            tick_data, load_error = _load_backtest_data(task, data_loader)

            if load_error:
                logger.error(load_error)
                execution.mark_failed(RuntimeError(load_error))
                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
                return {
                    "success": False,
                    "task_id": task_id,
                    "execution_id": execution.id,
                    "error": load_error,
                }

            instrument = task.config.parameters.get("instrument", [])

            # Get resource limits
            cpu_limit = get_config("backtesting.cpu_limit", 1)
            memory_limit = get_config("backtesting.memory_limit", 2147483648)  # 2GB

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

            # Run backtest
            logger.info("Running backtest engine for task %d", task_id)
            engine = BacktestEngine(backtest_config)
            trade_log, equity_curve, performance_metrics = engine.run(tick_data)

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
            task = TradingTask.objects.select_related("config", "user", "account").get(id=task_id)
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
            account=task.account,
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
            task.account.account_id,
        )

        # Initialize strategy executor
        # Note: The actual strategy execution happens via market data streaming
        # which is managed by the start_market_data_stream Celery task

        # Get instrument from configuration
        instrument = task.config.parameters.get("instrument", [])

        if not instrument:
            error_msg = "No instrument specified in configuration"
            logger.error(error_msg)
            execution.mark_failed(ValueError(error_msg))
            task.status = TaskStatus.FAILED
            task.save(update_fields=["status", "updated_at"])
            return {
                "success": False,
                "task_id": task_id,
                "execution_id": execution.id,
                "error": error_msg,
            }

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
            "account_id": task.account.account_id,
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
            task = TradingTask.objects.select_related("config", "account").get(id=task_id)
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
