"""
Celery tasks for market data streaming and trading operations.

This module contains Celery tasks for:
- Starting and managing market data streams from OANDA
- Processing tick data and broadcasting to strategy executors
- Managing one stream per active OANDA account

Requirements: 7.1, 7.2, 12.1
"""

# pylint: disable=too-many-lines

import logging
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.utils import timezone

from celery import shared_task

from accounts.models import OandaAccount
from trading.enums import TaskStatus
from trading.market_data_streamer import MarketDataStreamer, TickData
from trading.oanda_sync_task import oanda_sync_task  # noqa: F401  # pylint: disable=unused-import
from trading.tick_data_models import TickData as TickDataModel
from trading_system.config_loader import get_config

logger = logging.getLogger(__name__)

# Cache key prefix for active streams
STREAM_CACHE_PREFIX = "market_data_stream:"


class TickDataBuffer:
    """
    Buffer for batch insertion of tick data.

    This class accumulates tick data and performs batch insertions to the database
    for improved performance. It supports both size-based and time-based flushing.

    Requirements: 7.1, 7.2, 12.1
    """

    def __init__(
        self,
        account: OandaAccount,
        batch_size: int = 100,
        batch_timeout: float = 1.0,
    ):
        """
        Initialize the tick data buffer.

        Args:
            account: OandaAccount instance
            batch_size: Number of ticks to buffer before flushing (default: 100)
            batch_timeout: Maximum time in seconds to wait before flushing (default: 1.0)
        """
        self.account = account
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.buffer: List[TickDataModel] = []
        self.lock = threading.Lock()
        self.last_flush_time = time.time()
        self.total_stored = 0
        self.total_errors = 0

    def add_tick(self, tick: TickData) -> None:
        """
        Add a tick to the buffer.

        If the buffer reaches batch_size or batch_timeout has elapsed,
        the buffer will be flushed to the database.

        Args:
            tick: TickData object to add to buffer
        """
        with self.lock:
            try:
                # Create TickDataModel instance
                tick_model = TickDataModel(
                    account=self.account,
                    instrument=tick.instrument,
                    timestamp=self._parse_timestamp(tick.time),
                    bid=Decimal(str(tick.bid)),
                    ask=Decimal(str(tick.ask)),
                    mid=Decimal(str(tick.mid)),
                    spread=Decimal(str(tick.spread)),
                )

                self.buffer.append(tick_model)

                # Check if we should flush
                current_time = time.time()
                should_flush_size = len(self.buffer) >= self.batch_size
                should_flush_time = (current_time - self.last_flush_time) >= self.batch_timeout

                if should_flush_size or should_flush_time:
                    self._flush()

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error adding tick to buffer: %s", e, exc_info=True)
                self.total_errors += 1

    def _parse_timestamp(self, time_str: str) -> datetime:
        """
        Parse OANDA timestamp string to datetime object.

        Args:
            time_str: ISO 8601 timestamp string from OANDA

        Returns:
            Timezone-aware datetime object
        """
        # OANDA returns timestamps in RFC3339 format
        # Example: "2024-01-15T10:30:45.123456789Z"
        try:
            # Parse the timestamp
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            # Ensure it's timezone-aware
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            return dt
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error parsing timestamp '%s': %s", time_str, e)
            # Fallback to current time
            return timezone.now()

    def _flush(self) -> None:
        """
        Flush the buffer to the database using bulk_create.

        This method performs a batch insert of all buffered tick data.
        It handles database errors gracefully and logs the operation.
        """
        if not self.buffer:
            return

        buffer_size = len(self.buffer)

        try:
            # Use bulk_create for efficient batch insertion
            with transaction.atomic():
                TickDataModel.objects.bulk_create(
                    self.buffer,
                    batch_size=self.batch_size,
                    ignore_conflicts=False,
                )

            self.total_stored += buffer_size
            logger.info(
                "Flushed %d ticks to database for account %s (total stored: %d)",
                buffer_size,
                self.account.account_id,
                self.total_stored,
            )

        except DatabaseError as e:
            self.total_errors += buffer_size
            logger.error(
                "Database error flushing %d ticks for account %s: %s",
                buffer_size,
                self.account.account_id,
                e,
                exc_info=True,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.total_errors += buffer_size
            logger.error(
                "Unexpected error flushing %d ticks for account %s: %s",
                buffer_size,
                self.account.account_id,
                e,
                exc_info=True,
            )

        finally:
            # Clear the buffer and update flush time
            self.buffer.clear()
            self.last_flush_time = time.time()

    def flush(self) -> None:
        """
        Manually flush the buffer to the database.

        This is a public method that can be called to force a flush.
        """
        with self.lock:
            self._flush()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get buffer statistics.

        Returns:
            Dictionary with buffer statistics
        """
        with self.lock:
            return {
                "buffer_size": len(self.buffer),
                "total_stored": self.total_stored,
                "total_errors": self.total_errors,
                "last_flush_time": self.last_flush_time,
            }


@shared_task(bind=True, max_retries=3)
def start_market_data_stream(  # type: ignore[no-untyped-def]  # noqa: C901
    self,  # pylint: disable=unused-argument
    account_id: int,
    instrument: str,
) -> Dict[str, Any]:
    # pylint: disable=too-many-locals,too-many-statements
    """
    Start market data streaming for an OANDA account.

    This task manages one stream per active OANDA account. It:
    - Initializes a MarketDataStreamer instance
    - Starts streaming for specified instrument
    - Processes ticks and broadcasts to strategy executor
    - Stores ticks to database (if enabled in configuration)
    - Handles reconnection on failures

    Args:
        account_id: Primary key of the OandaAccount
        instrument: Currency pair to stream (e.g., 'EUR_USD')

    Returns:
        Dictionary containing:
            - success: Whether the stream was started successfully
            - account_id: OANDA account ID
            - instrument: Instrument being streamed
            - error: Error message if stream failed to start
            - tick_storage_enabled: Whether tick storage is enabled
            - tick_storage_stats: Statistics about tick storage (if enabled)

    Requirements: 7.1, 7.2, 12.1
    """
    tick_buffer = None

    try:
        # Fetch the OandaAccount from database
        try:
            oanda_account = OandaAccount.objects.get(id=account_id)
        except OandaAccount.DoesNotExist:
            error_msg = f"OandaAccount with id {account_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "account_id": None,
                "instrument": instrument,
                "error": error_msg,
            }

        # Check if account is active
        if not oanda_account.is_active:
            error_msg = f"Account {oanda_account.account_id} is not active"
            logger.warning(error_msg)
            return {
                "success": False,
                "account_id": oanda_account.account_id,
                "instrument": instrument,
                "error": error_msg,
            }

        # Check if a stream is already running for this account
        cache_key = f"{STREAM_CACHE_PREFIX}{account_id}"
        if cache.get(cache_key):
            logger.info(
                "Market data stream already running for account %s",
                oanda_account.account_id,
            )
            return {
                "success": True,
                "account_id": oanda_account.account_id,
                "instrument": instrument,
                "error": None,
                "message": "Stream already running",
            }

        # Load tick storage configuration
        tick_storage_enabled = get_config("tick_storage.enabled", True)
        batch_size = get_config("tick_storage.batch_size", 100)
        batch_timeout = get_config("tick_storage.batch_timeout", 1.0)

        logger.info(
            "Tick storage configuration: enabled=%s, batch_size=%d, batch_timeout=%.1fs",
            tick_storage_enabled,
            batch_size,
            batch_timeout,
        )

        # Initialize tick data buffer if storage is enabled
        if tick_storage_enabled:
            tick_buffer = TickDataBuffer(
                account=oanda_account,
                batch_size=batch_size,
                batch_timeout=batch_timeout,
            )
            logger.info(
                "Initialized tick data buffer for account %s",
                oanda_account.account_id,
            )

        # Create and initialize the market data streamer
        streamer = MarketDataStreamer(oanda_account)
        streamer.initialize_connection()

        # Register tick callback to process and broadcast ticks
        def on_tick(tick: TickData) -> None:
            """
            Process tick data and broadcast to strategy executor.

            This callback is called for each tick received from the stream.
            It will:
            1. Store tick to database (if enabled)
            2. Log the tick data
            3. Broadcast to strategy executor
            4. Broadcast to frontend via Django Channels

            Args:
                tick: Normalized tick data
            """
            # Store tick to database if enabled
            if tick_storage_enabled and tick_buffer:
                try:
                    tick_buffer.add_tick(tick)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Error storing tick for %s: %s",
                        tick.instrument,
                        e,
                        exc_info=True,
                    )

            logger.debug(
                "Received tick for %s: bid=%s, ask=%s, mid=%s",
                tick.instrument,
                tick.bid,
                tick.ask,
                tick.mid,
            )

            # Broadcast to strategy executor
            _broadcast_to_strategy_executors(oanda_account, tick)

            # Broadcast to frontend via Django Channels
            _broadcast_to_frontend(account_id, tick)

        streamer.register_tick_callback(on_tick)

        # Start the stream
        streamer.start_stream(instrument)

        # Mark stream as active in cache (expires after 1 hour)
        cache.set(cache_key, True, timeout=3600)

        logger.info(
            "Successfully started market data stream for account %s with instrument: %s",
            oanda_account.account_id,
            instrument,
        )

        # Process the stream (this will block until stream is stopped or fails)
        try:
            streamer.process_stream()
        except Exception as stream_error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error processing stream for account %s: %s",
                oanda_account.account_id,
                stream_error,
            )

            # Flush any remaining ticks before attempting reconnection
            if tick_buffer:
                logger.info("Flushing tick buffer before reconnection attempt")
                tick_buffer.flush()

            # Attempt reconnection
            if streamer.reconnect():
                logger.info(
                    "Successfully reconnected stream for account %s",
                    oanda_account.account_id,
                )
                # Continue processing after reconnection
                streamer.process_stream()
            else:
                # Reconnection failed, clean up and return error
                cache.delete(cache_key)
                raise

        # Get final tick storage statistics
        tick_storage_stats = None
        if tick_buffer:
            # Flush any remaining ticks
            tick_buffer.flush()
            tick_storage_stats = tick_buffer.get_stats()
            logger.info(
                "Final tick storage stats for account %s: %s",
                oanda_account.account_id,
                tick_storage_stats,
            )

        return {
            "success": True,
            "account_id": oanda_account.account_id,
            "instrument": instrument,
            "error": None,
            "tick_storage_enabled": tick_storage_enabled,
            "tick_storage_stats": tick_storage_stats,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to start market data stream: {str(e)}"
        logger.error(
            "Error starting market data stream for account %s: %s",
            account_id,
            error_msg,
            exc_info=True,
        )

        # Flush any remaining ticks before cleanup
        if tick_buffer:
            try:
                logger.info("Flushing tick buffer before cleanup")
                tick_buffer.flush()
            except Exception as flush_error:  # pylint: disable=broad-exception-caught
                logger.error("Error flushing tick buffer: %s", flush_error)

        # Clean up cache entry
        cache_key = f"{STREAM_CACHE_PREFIX}{account_id}"
        cache.delete(cache_key)

        return {
            "success": False,
            "account_id": account_id,
            "instrument": instrument,
            "error": error_msg,
        }


@shared_task
def stop_market_data_stream(account_id: int) -> Dict[str, Any]:
    """
    Stop market data streaming for an OANDA account.

    This task stops the active market data stream for the specified account
    and cleans up resources.

    Args:
        account_id: Primary key of the OandaAccount

    Returns:
        Dictionary containing:
            - success: Whether the stream was stopped successfully
            - account_id: OANDA account ID
            - error: Error message if stop failed

    Requirements: 7.1, 7.2
    """
    try:
        # Fetch the OandaAccount from database
        try:
            oanda_account = OandaAccount.objects.get(id=account_id)
        except OandaAccount.DoesNotExist:
            error_msg = f"OandaAccount with id {account_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "account_id": None,
                "error": error_msg,
            }

        # Check if a stream is running
        cache_key = f"{STREAM_CACHE_PREFIX}{account_id}"
        if not cache.get(cache_key):
            logger.info(
                "No active market data stream found for account %s",
                oanda_account.account_id,
            )
            return {
                "success": True,
                "account_id": oanda_account.account_id,
                "error": None,
                "message": "No active stream to stop",
            }

        # Remove cache entry to signal stream should stop
        cache.delete(cache_key)

        logger.info(
            "Stopped market data stream for account %s",
            oanda_account.account_id,
        )

        return {
            "success": True,
            "account_id": oanda_account.account_id,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to stop market data stream: {str(e)}"
        logger.error(
            "Error stopping market data stream for account %s: %s",
            account_id,
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "account_id": account_id,
            "error": error_msg,
        }


@shared_task
def get_stream_status(account_id: int) -> Dict[str, Any]:
    """
    Get the status of a market data stream for an OANDA account.

    Args:
        account_id: Primary key of the OandaAccount

    Returns:
        Dictionary containing:
            - is_active: Whether a stream is currently active
            - account_id: OANDA account ID
            - error: Error message if status check failed

    Requirements: 7.1, 7.2
    """
    try:
        # Fetch the OandaAccount from database
        try:
            oanda_account = OandaAccount.objects.get(id=account_id)
        except OandaAccount.DoesNotExist:
            error_msg = f"OandaAccount with id {account_id} does not exist"
            logger.error(error_msg)
            return {
                "is_active": False,
                "account_id": None,
                "error": error_msg,
            }

        # Check cache for active stream
        cache_key = f"{STREAM_CACHE_PREFIX}{account_id}"
        is_active = bool(cache.get(cache_key))

        return {
            "is_active": is_active,
            "account_id": oanda_account.account_id,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to get stream status: {str(e)}"
        logger.error(
            "Error getting stream status for account %s: %s",
            account_id,
            error_msg,
            exc_info=True,
        )

        return {
            "is_active": False,
            "account_id": account_id,
            "error": error_msg,
        }


@shared_task
def cleanup_old_tick_data(retention_days: int | None = None) -> Dict[str, Any]:
    """
    Delete tick data older than the retention period.

    This task is scheduled to run daily at 2 AM to clean up old tick data
    and prevent the database from growing indefinitely. The retention period
    can be configured via the TICK_DATA_RETENTION_DAYS setting (default: 90 days).

    Args:
        retention_days: Number of days to retain tick data (uses default if None)

    Returns:
        Dictionary containing:
            - success: Whether the cleanup was successful
            - deleted_count: Number of records deleted
            - retention_days: Retention period used
            - cutoff_date: Date before which data was deleted
            - error: Error message if cleanup failed

    Requirements: 7.1, 7.2
    """
    try:
        # Use default retention period if not specified
        if retention_days is None:
            retention_days = TickDataModel.get_retention_days()

        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        logger.info(
            "Starting tick data cleanup: retention_days=%d, cutoff_date=%s",
            retention_days,
            cutoff_date.isoformat(),
        )

        # Perform cleanup
        deleted_count = TickDataModel.cleanup_old_data(retention_days)

        logger.info(
            "Tick data cleanup completed: deleted %d records older than %s",
            deleted_count,
            cutoff_date.isoformat(),
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to cleanup old tick data: {str(e)}"
        logger.error(
            "Error during tick data cleanup: %s",
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "deleted_count": 0,
            "retention_days": retention_days,
            "cutoff_date": None,
            "error": error_msg,
        }


def _load_historical_data(
    config_dict: Dict[str, Any],
    start_date: datetime,
    end_date: datetime,
) -> list:
    """
    Load and combine historical data for the instrument.

    Args:
        config_dict: Configuration dictionary containing instrument
        start_date: Start date for data loading
        end_date: End date for data loading

    Returns:
        List of tick data sorted by timestamp
    """
    from trading.historical_data_loader import HistoricalDataLoader

    logger.info(
        "Loading historical data for instrument: %s",
        config_dict["instrument"],
    )
    data_loader = HistoricalDataLoader()

    # Load data for the instrument
    instrument = config_dict["instrument"]
    tick_data = data_loader.load_data(
        instrument=instrument,
        start_date=start_date,
        end_date=end_date,
    )

    # Sort by timestamp
    tick_data.sort(key=lambda t: t.timestamp)
    logger.info("Loaded %d tick data points", len(tick_data))

    return tick_data


def _create_backtest_config(
    config_dict: Dict[str, Any],
    start_date: datetime,
    end_date: datetime,
    cpu_limit: int,
    memory_limit: int,
) -> Any:
    """
    Create backtest configuration from config dictionary.

    Args:
        config_dict: Configuration dictionary
        start_date: Start date for backtest
        end_date: End date for backtest
        cpu_limit: CPU core limit
        memory_limit: Memory limit in bytes

    Returns:
        BacktestConfig instance
    """
    from trading.backtest_engine import BacktestConfig

    return BacktestConfig(
        strategy_type=config_dict["strategy_type"],
        strategy_config=config_dict["strategy_config"],
        instrument=config_dict["instrument"],
        start_date=start_date,
        end_date=end_date,
        initial_balance=Decimal(str(config_dict["initial_balance"])),
        commission_per_trade=Decimal(str(config_dict.get("commission_per_trade", 0))),
        cpu_limit=cpu_limit,
        memory_limit=memory_limit,
    )


def _calculate_performance_metrics(trade_log: list) -> Dict[str, Any]:
    """
    Calculate performance metrics from trade log.

    Args:
        trade_log: List of trade dictionaries

    Returns:
        Dictionary with performance metrics
    """
    total_trades = len(trade_log)
    winning_trades = sum(1 for trade in trade_log if trade["pnl"] > 0)
    losing_trades = sum(1 for trade in trade_log if trade["pnl"] < 0)
    total_pnl = sum(trade["pnl"] for trade in trade_log)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
    }


def _get_resource_usage(engine: Any, memory_limit: int, cpu_limit: int) -> Dict[str, Any]:
    """
    Get resource usage statistics from engine.

    Args:
        engine: BacktestEngine instance
        memory_limit: Memory limit in bytes
        cpu_limit: CPU core limit

    Returns:
        Dictionary with resource usage statistics
    """
    return {
        "peak_memory_mb": (
            engine.resource_monitor.get_peak_memory() / 1024 / 1024
            if engine.resource_monitor
            else 0
        ),
        "memory_limit_mb": memory_limit / 1024 / 1024,
        "cpu_limit_cores": cpu_limit,
    }


def _update_backtest_success(
    backtest: Any,
    metrics: Dict[str, Any],
    engine: Any,
    equity_curve: list,
    trade_log: list,
) -> None:
    """
    Update backtest model with successful results.

    Args:
        backtest: Backtest model instance
        metrics: Performance metrics dictionary
        engine: BacktestEngine instance
        equity_curve: Equity curve data
        trade_log: Trade log data
    """
    backtest.status = "completed"
    backtest.total_trades = metrics["total_trades"]
    backtest.winning_trades = metrics["winning_trades"]
    backtest.losing_trades = metrics["losing_trades"]
    backtest.total_return = float(metrics["total_pnl"])
    backtest.win_rate = metrics["win_rate"]
    backtest.final_balance = float(engine.balance)
    backtest.equity_curve = equity_curve
    backtest.trade_log = trade_log
    backtest.completed_at = timezone.now()
    backtest.save()


def _handle_resource_limit_error(
    backtest: Any,
    backtest_id: int,
    error: RuntimeError,
    engine: Any,
    memory_limit: int,
    cpu_limit: int,
) -> Dict[str, Any]:
    """
    Handle resource limit exceeded error.

    Args:
        backtest: Backtest model instance
        backtest_id: Backtest ID
        error: RuntimeError that was raised
        engine: BacktestEngine instance
        memory_limit: Memory limit in bytes
        cpu_limit: CPU core limit

    Returns:
        Error response dictionary
    """
    logger.error("Backtest %d terminated: %s", backtest_id, error)

    resource_usage = _get_resource_usage(engine, memory_limit, cpu_limit)

    backtest.status = TaskStatus.FAILED
    backtest.error_message = str(error)
    backtest.completed_at = timezone.now()
    backtest.save()

    return {
        "success": False,
        "backtest_id": backtest_id,
        "error": str(error),
        "resource_usage": resource_usage,
        "terminated": True,
    }


def _initialize_backtest(backtest_id: int) -> tuple[Any, Dict[str, Any] | None]:
    """
    Initialize and validate backtest instance.

    Args:
        backtest_id: Backtest ID

    Returns:
        Tuple of (backtest_instance, error_response or None)
    """
    from trading.backtest_models import Backtest

    try:
        backtest = Backtest.objects.get(id=backtest_id)
        backtest.status = "running"
        backtest.save(update_fields=["status"])
        return backtest, None
    except Backtest.DoesNotExist:
        error_msg = f"Backtest with id {backtest_id} does not exist"
        logger.error(error_msg)
        return None, {
            "success": False,
            "backtest_id": backtest_id,
            "error": error_msg,
        }


def _get_resource_limits() -> tuple:
    """
    Get resource limits from configuration.

    Returns:
        Tuple of (cpu_limit, memory_limit)
    """
    cpu_limit = get_config("backtesting.cpu_limit", 1)
    memory_limit = get_config("backtesting.memory_limit", 2147483648)  # 2GB

    logger.info(
        "Resource limits: CPU=%d cores, Memory=%dMB",
        cpu_limit,
        memory_limit / 1024 / 1024,
    )

    return cpu_limit, memory_limit


def _prepare_backtest_data(
    config_dict: Dict[str, Any],
) -> tuple:
    """
    Prepare backtest configuration and data.

    Args:
        config_dict: Configuration dictionary

    Returns:
        Tuple of (backtest_config, tick_data, cpu_limit, memory_limit)
    """
    cpu_limit, memory_limit = _get_resource_limits()

    start_date = datetime.fromisoformat(config_dict["start_date"])
    end_date = datetime.fromisoformat(config_dict["end_date"])

    backtest_config = _create_backtest_config(
        config_dict, start_date, end_date, cpu_limit, memory_limit
    )

    tick_data = _load_historical_data(config_dict, start_date, end_date)

    return backtest_config, tick_data, cpu_limit, memory_limit


def _execute_backtest(
    backtest: Any,
    backtest_id: int,
    engine: Any,
    tick_data: list,
    memory_limit: int,
    cpu_limit: int,
) -> Dict[str, Any]:
    """
    Execute backtest and return results.

    Args:
        backtest: Backtest model instance
        backtest_id: Backtest ID
        engine: BacktestEngine instance
        tick_data: Historical tick data
        memory_limit: Memory limit in bytes
        cpu_limit: CPU core limit

    Returns:
        Result dictionary
    """
    try:
        trade_log, equity_curve, performance_metrics = engine.run(tick_data)
        metrics = performance_metrics  # Use metrics from engine
        resource_usage = _get_resource_usage(engine, memory_limit, cpu_limit)

        logger.info(
            "Backtest %d completed: %d trades, final balance: %s, win rate: %.1f%%",
            backtest_id,
            metrics["total_trades"],
            engine.balance,
            metrics["win_rate"],
        )

        _update_backtest_success(backtest, metrics, engine, equity_curve, trade_log)

        return {
            "success": True,
            "backtest_id": backtest_id,
            "trade_count": metrics["total_trades"],
            "final_balance": float(engine.balance),
            "total_return": float(metrics["total_pnl"]),
            "win_rate": metrics["win_rate"],
            "resource_usage": resource_usage,
            "error": None,
            "terminated": False,
        }

    except RuntimeError as e:
        if "memory limit exceeded" in str(e):
            return _handle_resource_limit_error(
                backtest, backtest_id, e, engine, memory_limit, cpu_limit
            )
        raise


@shared_task(
    bind=True,
    time_limit=3600,  # 1 hour hard limit
    soft_time_limit=3300,  # 55 minutes soft limit
)
def run_backtest_task(  # type: ignore[no-untyped-def]
    self,  # pylint: disable=unused-argument
    backtest_id: int,
    config_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a backtest with resource limits.

    This task runs a backtest with configured CPU and memory limits.
    It monitors resource usage during execution and terminates the backtest
    if limits are exceeded.

    Resource limits are configured in system.yaml:
    - cpu_limit: Number of CPU cores (default: 1)
    - memory_limit: Memory limit in bytes (default: 2GB)

    Args:
        backtest_id: Primary key of the Backtest model instance
        config_dict: Dictionary containing backtest configuration:
            - strategy_type: Type of strategy to backtest
            - strategy_config: Strategy configuration parameters
            - instrument: Currency pair
            - start_date: Start date (ISO format string)
            - end_date: End date (ISO format string)
            - initial_balance: Initial account balance
            - commission_per_trade: Commission per trade (optional,
              bid/ask spread already in tick data)

    Returns:
        Dictionary containing:
            - success: Whether the backtest completed successfully
            - backtest_id: Backtest ID
            - trade_count: Number of trades executed
            - final_balance: Final account balance
            - resource_usage: Resource usage statistics
            - error: Error message if backtest failed
            - terminated: Whether backtest was terminated due to resource limits

    Requirements: 12.2, 12.3
    """
    from trading.backtest_engine import BacktestEngine
    from trading.backtest_models import Backtest

    try:
        # Initialize backtest
        backtest, error_response = _initialize_backtest(backtest_id)
        if error_response:
            return error_response

        logger.info(
            "Starting backtest %d: %s from %s to %s",
            backtest_id,
            config_dict.get("strategy_type"),
            config_dict.get("start_date"),
            config_dict.get("end_date"),
        )

        # Prepare backtest configuration and data
        backtest_config, tick_data, cpu_limit, memory_limit = _prepare_backtest_data(config_dict)

        if not tick_data:
            error_msg = "No historical data available for the specified period"
            logger.error(error_msg)
            backtest.status = "failed"
            backtest.error_message = error_msg
            backtest.save(update_fields=["status", "error_message"])
            return {
                "success": False,
                "backtest_id": backtest_id,
                "error": error_msg,
            }

        # Create and run backtest engine
        return _execute_backtest(
            backtest,
            backtest_id,
            BacktestEngine(backtest_config),
            tick_data,
            memory_limit,
            cpu_limit,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Backtest failed: {str(e)}"
        logger.error(
            "Error running backtest %d: %s",
            backtest_id,
            error_msg,
            exc_info=True,
        )

        # Update backtest status
        try:
            backtest = Backtest.objects.get(id=backtest_id)
            backtest.status = "failed"
            backtest.error_message = error_msg
            backtest.completed_at = timezone.now()
            backtest.save()
        except Exception as save_error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to update backtest status: %s", save_error)

        return {
            "success": False,
            "backtest_id": backtest_id,
            "error": error_msg,
            "terminated": False,
        }


@shared_task
def run_host_access_monitoring() -> Dict[str, Any]:
    """
    Run host-level access monitoring checks.

    This task performs periodic monitoring of:
    - SSH connection attempts
    - Docker exec commands
    - Sensitive file access
    - Port scanning detection

    This task should be scheduled to run every 5 minutes via Celery Beat.

    Returns:
        Dictionary containing:
            - success: Whether monitoring completed successfully
            - error: Error message if monitoring failed

    Requirements: 36.1, 36.2, 36.3, 36.4, 36.5
    """
    from trading.host_access_monitor import HostAccessMonitor

    try:
        logger.info("Starting host-level access monitoring")

        monitor = HostAccessMonitor()
        monitor.run_all_monitors()

        logger.info("Host-level access monitoring completed successfully")

        return {
            "success": True,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Host access monitoring failed: {str(e)}"
        logger.error(
            "Error in host access monitoring: %s",
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "error": error_msg,
        }


def _broadcast_to_strategy_executors(account: OandaAccount, tick: TickData) -> None:
    """
    Broadcast tick data to all active strategy executors for the account.

    This function finds all active strategies for the account and processes
    the tick through each strategy's executor.

    Args:
        account: OandaAccount instance
        tick: TickData to broadcast

    Requirements: 6.5
    """
    from trading.models import Strategy
    from trading.strategy_executor import StrategyExecutor

    try:
        # Get all active strategies for this account
        active_strategies = Strategy.objects.filter(account=account, is_active=True)

        if not active_strategies.exists():
            logger.debug(
                "No active strategies for account %s, skipping tick broadcast", account.account_id
            )
            return

        # Convert TickData to TickDataModel for strategy executor
        tick_model = TickDataModel(
            account=account,
            instrument=tick.instrument,
            timestamp=_parse_tick_timestamp(tick.time),
            bid=Decimal(str(tick.bid)),
            ask=Decimal(str(tick.ask)),
            mid=Decimal(str(tick.mid)),
            spread=Decimal(str(tick.spread)),
        )

        # Process tick through each active strategy
        for strategy in active_strategies:
            try:
                # Check if this instrument is in the strategy's instrument
                if tick.instrument not in strategy.instrument:
                    continue

                executor = StrategyExecutor(strategy)
                orders = executor.process_tick(tick_model)

                if orders:
                    logger.info(
                        "Strategy %s generated %d orders for %s",
                        strategy.id,
                        len(orders),
                        tick.instrument,
                    )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error processing tick for strategy %s: %s", strategy.id, e, exc_info=True
                )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error broadcasting tick to strategy executors: %s", e, exc_info=True)


def _broadcast_to_frontend(account_id: int, tick: TickData) -> None:
    """
    Broadcast tick data to frontend clients via Django Channels.

    This function sends tick updates to all WebSocket clients subscribed
    to the account's market data channel.

    Args:
        account_id: OANDA account ID (primary key)
        tick: TickData to broadcast

    Requirements: 5.4
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    try:
        channel_layer = get_channel_layer()

        if channel_layer is None:
            logger.warning("Channel layer not configured, skipping frontend broadcast")
            return

        # Send tick data to the account's channel group
        group_name = f"market_data_{account_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "market_data_update",
                "data": tick.to_dict(),
            },
        )

        logger.debug("Broadcasted tick for %s to frontend group %s", tick.instrument, group_name)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error broadcasting tick to frontend: %s", e, exc_info=True)


def _parse_tick_timestamp(time_str: str) -> datetime:
    """
    Parse OANDA timestamp string to datetime object.

    Args:
        time_str: ISO 8601 timestamp string from OANDA

    Returns:
        Timezone-aware datetime object
    """
    try:
        # Parse the timestamp
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        # Ensure it's timezone-aware
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error parsing timestamp '%s': %s", time_str, e)
        # Fallback to current time
        return timezone.now()


@shared_task(
    bind=True,
    time_limit=3600,  # 1 hour hard limit
    soft_time_limit=3300,  # 55 minutes soft limit
)
def run_backtest_task_v2(  # type: ignore[no-untyped-def]
    self,  # pylint: disable=unused-argument
    task_id: int,
) -> Dict[str, Any]:
    """
    Execute a BacktestTask with resource limits.

    This is the new version that works with the BacktestTask model from
    the task-based strategy configuration feature.

    This task:
    1. Creates a TaskExecution record at start
    2. Updates execution status during processing
    3. Creates ExecutionMetrics on completion
    4. Handles rerun logic

    Args:
        task_id: Primary key of the BacktestTask model instance

    Returns:
        Dictionary containing:
            - success: Whether the backtest completed successfully
            - task_id: BacktestTask ID
            - execution_id: TaskExecution ID
            - metrics: Performance metrics (if successful)
            - error: Error message (if backtest failed)

    Requirements: 4.1, 4.5, 4.6, 7.1, 7.3
    """
    from trading.services.task_executor import execute_backtest_task

    logger.info("Starting BacktestTask execution for task_id=%d", task_id)

    try:
        result = execute_backtest_task(task_id)

        if result["success"]:
            logger.info(
                "BacktestTask %d execution completed successfully: execution_id=%d",
                task_id,
                result["execution_id"],
            )
        else:
            logger.error(
                "BacktestTask %d execution failed: %s",
                task_id,
                result.get("error"),
            )

        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"BacktestTask execution failed: {str(e)}"
        logger.error(
            "Error in run_backtest_task_v2 for task_id=%d: %s",
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


@shared_task
def run_trading_task_v2(task_id: int) -> Dict[str, Any]:
    """
    Execute a TradingTask.

    This is the new version that works with the TradingTask model from
    the task-based strategy configuration feature.

    This task:
    1. Creates a TaskExecution record at start
    2. Integrates with existing strategy executor
    3. Updates execution status during processing
    4. Creates ExecutionMetrics periodically
    5. Handles pause/resume logic

    Args:
        task_id: Primary key of the TradingTask model instance

    Returns:
        Dictionary containing:
            - success: Whether the task started successfully
            - task_id: TradingTask ID
            - execution_id: TaskExecution ID
            - account_id: OANDA account ID
            - instrument: List of instrument to trade
            - error: Error message (if failed)

    Requirements: 4.2, 4.3, 4.4, 4.5, 7.2, 7.3
    """
    from trading.services.task_executor import execute_trading_task

    logger.info("Starting TradingTask execution for task_id=%d", task_id)

    try:
        result = execute_trading_task(task_id)

        if result["success"]:
            logger.info(
                "TradingTask %d execution started successfully: execution_id=%d, account=%s",
                task_id,
                result["execution_id"],
                result.get("account_id"),
            )

            # Start market data streaming for the account
            account_id = result.get("account_id")
            instrument = result.get("instrument", [])

            if account_id and instrument:
                # Trigger market data streaming
                start_market_data_stream.delay(account_id, instrument)
                logger.info(
                    "Started market data streaming for account %s with instrument: %s",
                    account_id,
                    ", ".join(instrument),
                )
        else:
            logger.error(
                "TradingTask %d execution failed: %s",
                task_id,
                result.get("error"),
            )

        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"TradingTask execution failed: {str(e)}"
        logger.error(
            "Error in run_trading_task_v2 for task_id=%d: %s",
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


@shared_task
def stop_trading_task_v2(task_id: int) -> Dict[str, Any]:
    """
    Stop a running TradingTask.

    Args:
        task_id: Primary key of the TradingTask model instance

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.3, 7.2, 7.3
    """
    from trading.services.task_executor import stop_trading_task_execution
    from trading.trading_task_models import TradingTask

    logger.info("Stopping TradingTask for task_id=%d", task_id)

    try:
        # Get the task to find the account
        task = TradingTask.objects.select_related("oanda_account").get(id=task_id)

        # Stop the task execution
        result = stop_trading_task_execution(task_id)

        if result["success"]:
            # Stop market data streaming for the account
            stop_market_data_stream.delay(task.oanda_account.id)
            logger.info(
                "Stopped market data streaming for account %s",
                task.oanda_account.account_id,
            )

        return result

    except TradingTask.DoesNotExist:
        error_msg = f"TradingTask with id {task_id} does not exist"
        logger.error(error_msg)
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to stop TradingTask: {str(e)}"
        logger.error(
            "Error in stop_trading_task_v2 for task_id=%d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }


@shared_task
def pause_trading_task_v2(task_id: int) -> Dict[str, Any]:
    """
    Pause a running TradingTask.

    Args:
        task_id: Primary key of the TradingTask model instance

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.4, 7.3
    """
    from trading.services.task_executor import pause_trading_task_execution

    logger.info("Pausing TradingTask for task_id=%d", task_id)

    try:
        result = pause_trading_task_execution(task_id)
        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to pause TradingTask: {str(e)}"
        logger.error(
            "Error in pause_trading_task_v2 for task_id=%d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }


@shared_task
def resume_trading_task_v2(task_id: int) -> Dict[str, Any]:
    """
    Resume a paused TradingTask.

    Args:
        task_id: Primary key of the TradingTask model instance

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.4, 7.3
    """
    from trading.services.task_executor import resume_trading_task_execution

    logger.info("Resuming TradingTask for task_id=%d", task_id)

    try:
        result = resume_trading_task_execution(task_id)
        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to resume TradingTask: {str(e)}"
        logger.error(
            "Error in resume_trading_task_v2 for task_id=%d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
        }
