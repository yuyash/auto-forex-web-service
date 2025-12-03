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
from trading.athena_import_task import (  # noqa: F401  # pylint: disable=unused-import
    import_athena_data_daily,
)
from trading.enums import TaskStatus
from trading.market_data_streamer import MarketDataStreamer, TickData
from trading.oanda_sync_task import oanda_sync_task  # noqa: F401  # pylint: disable=unused-import
from trading.result_models import PerformanceMetrics
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
        log_interval: int = 1000,
    ):
        """
        Initialize the tick data buffer.

        Args:
            account: OandaAccount instance
            batch_size: Number of ticks to buffer before flushing (default: 100)
            batch_timeout: Maximum time in seconds to wait before flushing (default: 1.0)
            log_interval: Log at INFO level every N ticks stored (default: 1000)
        """
        self.account = account
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.log_interval = log_interval
        self.buffer: List[TickDataModel] = []
        self.lock = threading.Lock()
        self.last_flush_time = time.time()
        self.total_stored = 0
        self.total_errors = 0
        self._last_logged_total = 0

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

            # Log at DEBUG level for each flush, INFO only at intervals
            if self.total_stored - self._last_logged_total >= self.log_interval:
                logger.info(
                    "Tick storage progress for account %s: %d ticks stored",
                    self.account.account_id,
                    self.total_stored,
                )
                self._last_logged_total = self.total_stored
            else:
                logger.debug(
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


# Time limits for long-running tasks
# Note: Celery decorators are evaluated at import time, so we can't dynamically
# read from SystemSettings. These values should match SystemSettings defaults.
# For streaming tasks (market data, trading): use effectively unlimited (10 years)
# For backtest tasks: use SystemSettings.celery_task_soft/hard_time_limit defaults
STREAMING_TIME_LIMIT = 10 * 365 * 24 * 60 * 60  # 315,360,000 seconds (10 years)
BACKTEST_SOFT_TIME_LIMIT = 259200  # 72 hours (matches SystemSettings default)
BACKTEST_HARD_TIME_LIMIT = 259200  # 72 hours (matches SystemSettings default)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=STREAMING_TIME_LIMIT,
    time_limit=STREAMING_TIME_LIMIT + 3600,  # 1 hour buffer
)
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

        # Track tick count for periodic logging
        stream_tick_count = [0]  # Use list to allow modification in nested function
        stream_last_log_time = [time.time()]

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
            stream_tick_count[0] += 1
            current_time = time.time()

            # Log first tick and then every 100 ticks or every 60 seconds
            is_first_tick = stream_tick_count[0] == 1
            should_log = (
                is_first_tick
                or stream_tick_count[0] % 100 == 0
                or (current_time - stream_last_log_time[0]) >= 60
            )

            if should_log:
                stream_last_log_time[0] = current_time
                if is_first_tick:
                    logger.info(
                        "First tick received from stream for account %s: %s @ %s",
                        oanda_account.account_id,
                        tick.instrument,
                        tick.mid,
                    )
                else:
                    logger.info(
                        "Stream tick count for account %s: %d (latest: %s @ %s)",
                        oanda_account.account_id,
                        stream_tick_count[0],
                        tick.instrument,
                        tick.mid,
                    )

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

        logger.info(
            "Stream error handled gracefully for account %s. "
            "Resources cleaned up, task will be retried if configured.",
            account_id,
        )

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


@shared_task(bind=True, max_retries=3)
def collect_tick_data_for_default_account(
    self: Any,  # pylint: disable=unused-argument
    user_id: int,
    instruments: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Collect tick data for the user's default OANDA account.

    This task starts a market data stream for the default account and stores
    tick data to the database. It's automatically started when a default account
    is set and stopped when the default account is changed or removed.

    Args:
        user_id: ID of the user whose default account to use
        instruments: List of instruments to stream (default: all active instruments)

    Returns:
        Dictionary containing:
            - success: Whether the stream was started successfully
            - account_id: ID of the default account
            - instruments: List of instruments being streamed
            - error: Error message if stream failed to start

    Requirements: 7.1, 7.2, 12.1
    """
    try:
        # Get the user's default account
        default_account = OandaAccount.objects.filter(
            user_id=user_id, is_default=True, is_active=True
        ).first()

        if not default_account:
            error_msg = f"No default account found for user {user_id}"
            logger.warning(error_msg)
            return {
                "success": False,
                "account_id": None,
                "instruments": [],
                "error": error_msg,
            }

        # Use provided instruments or get from system settings
        if instruments is None:
            from accounts.models import SystemSettings

            try:
                settings = SystemSettings.get_settings()
                if settings and hasattr(settings, "tick_data_instruments"):
                    instruments_str = getattr(settings, "tick_data_instruments", "")
                    if instruments_str:
                        instruments = [i.strip() for i in instruments_str.split(",")]
                    else:
                        # Fallback to defaults if field is empty
                        instruments = [
                            "EUR_USD",
                            "GBP_USD",
                            "USD_JPY",
                            "USD_CHF",
                            "AUD_USD",
                            "USD_CAD",
                            "NZD_USD",
                        ]
                else:
                    # Fallback to defaults if settings not available
                    instruments = [
                        "EUR_USD",
                        "GBP_USD",
                        "USD_JPY",
                        "USD_CHF",
                        "AUD_USD",
                        "USD_CAD",
                        "NZD_USD",
                    ]
            except Exception:  # pylint: disable=broad-exception-caught
                # Fallback to defaults on any error
                instruments = [
                    "EUR_USD",
                    "GBP_USD",
                    "USD_JPY",
                    "USD_CHF",
                    "AUD_USD",
                    "USD_CAD",
                    "NZD_USD",
                ]

        logger.info(
            "Starting tick data collection for default account %s (user: %d, instruments: %s)",
            default_account.account_id,
            user_id,
            instruments,
        )

        # Start the market data stream for each instrument
        task_ids = []
        for instrument in instruments:
            result = start_market_data_stream.delay(
                account_id=default_account.pk, instrument=instrument
            )
            task_ids.append(result.id)
            logger.info(
                "Started tick data stream for %s on account %s (task: %s)",
                instrument,
                default_account.account_id,
                result.id,
            )

        logger.info(
            "Tick data collection started for account %s (%d streams)",
            default_account.account_id,
            len(task_ids),
        )

        return {
            "success": True,
            "account_id": default_account.pk,
            "instruments": instruments,
            "task_ids": task_ids,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to start tick data collection: {str(e)}"
        logger.error(
            "Error starting tick data collection for user %d: %s",
            user_id,
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "account_id": None,
            "instruments": [],
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
    metrics: PerformanceMetrics,
    engine: Any,
    equity_curve: list,
    trade_log: list,
) -> None:
    """
    Update backtest model with successful results.

    Args:
        backtest: Backtest model instance
        metrics: PerformanceMetrics dataclass
        engine: BacktestEngine instance
        equity_curve: Equity curve data
        trade_log: Trade log data
    """
    backtest.status = "completed"
    backtest.total_trades = metrics.total_trades
    backtest.winning_trades = metrics.winning_trades
    backtest.losing_trades = metrics.losing_trades
    backtest.total_return = float(metrics.total_pnl)
    backtest.win_rate = metrics.win_rate
    backtest.final_balance = float(engine.balance)
    backtest.equity_curve = equity_curve
    backtest.trade_log = trade_log
    backtest.strategy_events = metrics.strategy_events
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
    Get resource limits from SystemSettings or configuration fallback.

    Returns:
        Tuple of (cpu_limit, memory_limit)
    """
    from accounts.models import SystemSettings

    try:
        settings = SystemSettings.get_settings()
        cpu_limit = settings.backtest_cpu_limit
        memory_limit = settings.backtest_memory_limit
    except Exception:  # pylint: disable=broad-exception-caught
        # Fallback to config file if SystemSettings not available
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
        trade_log, equity_curve, performance_metrics = engine.run(tick_data, backtest=backtest)
        metrics = performance_metrics  # Use metrics from engine
        resource_usage = _get_resource_usage(engine, memory_limit, cpu_limit)

        logger.info(
            "Backtest %d completed: %d trades, final balance: %s, win rate: %.1f%%",
            backtest_id,
            metrics.total_trades,
            engine.balance,
            metrics.win_rate,
        )

        _update_backtest_success(backtest, metrics, engine, equity_curve, trade_log)

        return {
            "success": True,
            "backtest_id": backtest_id,
            "trade_count": metrics.total_trades,
            "final_balance": float(engine.balance),
            "total_return": float(metrics.total_pnl),
            "win_rate": metrics.win_rate,
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


def _get_task_execution(task: Any) -> Any:
    """Get the latest running execution for a task."""
    from trading.enums import TaskType
    from trading.execution_models import TaskExecution

    return TaskExecution.objects.filter(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        status=TaskStatus.RUNNING,
    ).first()


# Track tick counts per task for periodic logging
_task_tick_counts: dict[int, int] = {}
_task_last_log_time: dict[int, float] = {}

# Track tick counts for broadcast logging (per account)
_task_log_counts: dict[int, int] = {}

# Cache strategy instances per task to maintain state across ticks
_strategy_instances: dict[int, Any] = {}

# Track last metrics update time per task
_task_last_metrics_time: dict[int, float] = {}


def _update_trading_task_metrics(  # pylint: disable=too-many-locals
    task: Any, execution: Any
) -> None:
    """
    Update performance metrics for a trading task.

    Calculates current P&L from open positions and closed trades,
    then updates or creates ExecutionMetrics record.

    Args:
        task: TradingTask instance
        execution: TaskExecution instance
    """
    from trading.execution_models import ExecutionMetrics
    from trading.models import Position, Trade

    try:
        # Get open positions for this task
        open_positions = Position.objects.filter(
            trading_task=task,
            closed_at__isnull=True,
        )

        # Calculate unrealized P&L from open positions
        unrealized_pnl = sum(pos.unrealized_pnl or Decimal("0") for pos in open_positions)

        # Get closed trades for this task's execution
        closed_trades = Trade.objects.filter(
            account=task.oanda_account,
            opened_at__gte=execution.started_at if execution.started_at else timezone.now(),
        )

        # Calculate realized P&L and trade stats
        realized_pnl = Decimal("0")
        winning_trades = 0
        losing_trades = 0

        for trade in closed_trades:
            realized_pnl += trade.pnl or Decimal("0")
            if trade.pnl and trade.pnl > 0:
                winning_trades += 1
            elif trade.pnl and trade.pnl < 0:
                losing_trades += 1

        total_trades = closed_trades.count()
        total_pnl = realized_pnl + unrealized_pnl
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else Decimal("0")

        # For trading tasks, delete existing metrics and create new ones
        # (ExecutionMetrics is immutable, so we can't update in place)
        existing_metrics = ExecutionMetrics.objects.filter(execution=execution).first()
        if existing_metrics:
            existing_metrics.delete()

        ExecutionMetrics.objects.create(
            execution=execution,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
        )

        logger.debug(
            "Updated metrics for task %d: P&L=%s, trades=%d",
            task.pk,
            total_pnl,
            total_trades,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error updating metrics for task %d: %s", task.pk, e)


# pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks
def _process_tick_for_task(  # noqa: C901
    task: Any, tick: "TickData", tick_model: "TickDataModel", registry: Any
) -> None:
    import uuid

    # Get execution for logging
    execution = _get_task_execution(task)

    try:
        # Track tick count for periodic logging
        task_id = task.pk
        if task_id not in _task_tick_counts:
            _task_tick_counts[task_id] = 0
            _task_last_log_time[task_id] = time.time()
            # Log first tick received for this task
            first_tick_msg = (
                f"First tick received for task {task_id}: "
                f"{tick.instrument} bid={tick.bid} ask={tick.ask} mid={tick.mid}"
            )
            logger.info(first_tick_msg)
            if execution:
                execution.add_log("INFO", first_tick_msg)

        _task_tick_counts[task_id] += 1
        tick_count = _task_tick_counts[task_id]

        # Log every 50 ticks or every 30 seconds for better visibility
        current_time = time.time()
        should_log_progress = (
            tick_count % 50 == 0 or (current_time - _task_last_log_time[task_id]) >= 30
        )

        if should_log_progress:
            _task_last_log_time[task_id] = current_time
            progress_msg = (
                f"Task {task_id} processed {tick_count} ticks. "
                f"Latest: {tick.instrument} @ {tick.mid} (spread: {tick.spread})"
            )
            # Only log to server, not to frontend execution logs (too noisy)
            logger.info(progress_msg)

        # Get instrument from configuration
        task_instrument = task.config.parameters.get("instrument")
        if not task_instrument:
            warning_msg = f"Task {task_id} has no instrument configured"
            logger.warning(warning_msg)
            if execution and tick_count == 1:
                execution.add_log("WARNING", warning_msg)
            return

        if tick.instrument != task_instrument:
            # Only log instrument mismatch on first occurrence
            if tick_count <= 5:
                logger.debug(
                    "Tick instrument %s doesn't match task %d instrument %s",
                    tick.instrument,
                    task.pk,
                    task_instrument,
                )
            return

        # Get or create cached strategy instance to maintain state across ticks
        if task_id not in _strategy_instances:
            # Get strategy class from registry
            strategy_class = registry.get_strategy_class(task.config.strategy_type)
            if not strategy_class:
                warning_msg = (
                    f"Unknown strategy type '{task.config.strategy_type}' for task {task.pk}"
                )
                logger.warning(warning_msg)
                if execution:
                    execution.add_log("WARNING", warning_msg)
                return

            # Create and cache strategy instance
            _strategy_instances[task_id] = strategy_class(task)
            init_msg = (
                f"Strategy '{task.config.strategy_type}' initialized for task {task_id} "
                f"on instrument {task_instrument}"
            )
            logger.info(init_msg)
            if execution:
                execution.add_log("INFO", init_msg)

        strategy_instance = _strategy_instances[task_id]

        logger.debug(
            "Processing tick for task %d with strategy %s @ %s",
            task.pk,
            task.config.strategy_type,
            tick.mid,
        )

        # Process tick through strategy
        try:
            orders = strategy_instance.on_tick(tick_model)
        except Exception as strategy_error:
            error_msg = f"Strategy error processing tick: {str(strategy_error)}"
            logger.error(error_msg, exc_info=True)
            if execution:
                execution.add_log("ERROR", error_msg)
            return

        # Log when strategy processes tick but generates no orders (periodically)
        if not orders and tick_count % 100 == 0:
            # Count open positions for this task
            from trading.models import Position

            open_positions_count = Position.objects.filter(
                trading_task=task,
                closed_at__isnull=True,
            ).count()

            # Get realized and unrealized P&L
            from django.db.models import Sum

            realized_pnl = Position.objects.filter(
                trading_task=task,
                closed_at__isnull=False,
            ).aggregate(total=Sum("realized_pnl"))["total"] or Decimal("0")

            unrealized_pnl = Position.objects.filter(
                trading_task=task,
                closed_at__isnull=True,
            ).aggregate(total=Sum("unrealized_pnl"))["total"] or Decimal("0")

            # Get floor strategy layer info if available
            layer_info = ""
            if hasattr(strategy_instance, "layer_manager"):
                active_layers = [
                    layer for layer in strategy_instance.layer_manager.layers if layer.is_active
                ]
                if active_layers:
                    current_layer = active_layers[-1]  # Most recent active layer
                    layer_info = (
                        f"Layer {current_layer.layer_number} | "
                        f"Retracements: {current_layer.retracement_count}/"
                        f"{current_layer.max_retracements_per_layer} | "
                    )

            no_order_msg = (
                f"Tick #{tick_count} | {layer_info}"
                f"Open: {open_positions_count} | "
                f"Realized P&L: ${realized_pnl:.2f} | "
                f"Unrealized P&L: ${unrealized_pnl:.2f}"
            )
            logger.info(no_order_msg)
            if execution:
                execution.add_log("INFO", no_order_msg)

        if orders:
            order_msg = (
                f"Strategy generated {len(orders)} order(s) for {tick.instrument} @ {tick.mid}"
            )
            logger.info(order_msg)
            if execution:
                execution.add_log("INFO", order_msg)

            # Save orders to database and execute them
            from trading.order_executor import OrderExecutor

            saved_orders = []
            with transaction.atomic():
                for order in orders:
                    # Ensure order has required fields
                    order.account = task.oanda_account
                    order.trading_task = task

                    # Generate unique order ID if not set
                    if not order.order_id:
                        order.order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"

                    # Set default status if not set
                    if not order.status:
                        order.status = "pending"

                    # Save order
                    order.save()
                    saved_orders.append(order)

                    save_msg = (
                        f"Order saved: {order.order_id} - {order.direction.upper()} "
                        f"{order.units} {order.instrument} @ {order.price}"
                    )
                    logger.info(save_msg)
                    if execution:
                        execution.add_log("INFO", save_msg)

            # Execute orders via OANDA API
            if saved_orders:
                try:
                    executor = OrderExecutor(task.oanda_account)
                    for order in saved_orders:
                        if order.order_type == "market":
                            exec_msg = (
                                f"Executing market order: {order.direction.upper()} "
                                f"{order.units} {order.instrument}"
                            )
                            logger.info(exec_msg)
                            if execution:
                                execution.add_log("INFO", exec_msg)

                            result = executor.submit_market_order(
                                instrument=order.instrument,
                                units=order.units if order.direction == "long" else -order.units,
                                take_profit=order.take_profit,
                                stop_loss=order.stop_loss,
                            )

                            success_msg = f"Order executed successfully: {result.order_id}"
                            logger.info(success_msg)
                            if execution:
                                execution.add_log("INFO", success_msg)

                            # Check if this is a close order or an open order
                            from trading.models import Position
                            from trading.position_manager import PositionManager

                            is_close_order = getattr(order, "is_close_order", False)
                            closing_position_id = getattr(order, "closing_position_id", None)

                            if is_close_order and closing_position_id:
                                # Close the existing position
                                try:
                                    existing_position = Position.objects.get(
                                        position_id=closing_position_id,
                                        account=task.oanda_account,
                                        closed_at__isnull=True,
                                    )
                                    closed_pos = PositionManager.close_position(
                                        position=existing_position,
                                        exit_price=tick_model.mid,
                                        create_trade_record=True,
                                    )
                                    close_msg = (
                                        f"Position closed: {closed_pos.position_id} - "
                                        f"P&L: {closed_pos.realized_pnl}"
                                    )
                                    logger.info(close_msg)
                                    if execution:
                                        execution.add_log("INFO", close_msg)
                                except Position.DoesNotExist:
                                    warn_msg = (
                                        f"Position {closing_position_id} not found for closing"
                                    )
                                    logger.warning(warn_msg)
                                    if execution:
                                        execution.add_log("WARNING", warn_msg)
                            else:
                                # Create new Position record for the filled order
                                position = PositionManager.create_position(
                                    account=task.oanda_account,
                                    order=result,
                                    fill_price=tick_model.mid,
                                    strategy=(
                                        strategy_instance.strategy if strategy_instance else None
                                    ),
                                    layer_number=getattr(order, "layer_number", 1),
                                    is_first_lot=getattr(order, "is_first_lot", False),
                                )
                                # Link position to trading task
                                position.trading_task = task
                                position.save(update_fields=["trading_task"])

                                pos_msg = (
                                    f"Position created: {position.position_id} - "
                                    f"{position.direction} {position.units} {position.instrument}"
                                )
                                logger.info(pos_msg)
                                if execution:
                                    execution.add_log("INFO", pos_msg)
                        # Add support for other order types as needed
                except Exception as exec_error:
                    error_msg = f"Error executing orders: {str(exec_error)}"
                    logger.error(error_msg, exc_info=True)
                    if execution:
                        execution.add_log("ERROR", error_msg)

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Error processing tick for task {task.pk}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if execution:
            execution.add_log("ERROR", error_msg)

    # Periodically update performance metrics
    try:
        from accounts.models import SystemSettings

        settings = SystemSettings.get_settings()
        metrics_interval = settings.trading_metrics_interval_seconds

        current_time = time.time()
        last_metrics_time = _task_last_metrics_time.get(task_id, 0)

        if current_time - last_metrics_time >= metrics_interval:
            _task_last_metrics_time[task_id] = current_time
            if execution:
                _update_trading_task_metrics(task, execution)
    except Exception as metrics_error:  # pylint: disable=broad-exception-caught
        logger.debug("Error updating metrics: %s", metrics_error)


def _broadcast_to_strategy_executors(  # pylint: disable=too-many-locals
    account: OandaAccount, tick: TickData
) -> None:
    """
    Broadcast tick data to all active strategy executors for the account.

    This function finds all active strategies and running trading tasks for the account
    and processes the tick through each strategy's executor.

    Args:
        account: OandaAccount instance
        tick: TickData to broadcast

    Requirements: 6.5
    """
    from trading.models import Strategy
    from trading.strategy_executor import StrategyExecutor
    from trading.strategy_registry import registry
    from trading.trading_task_models import TradingTask

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

    # Process tick through running TradingTask objects
    try:
        running_tasks = TradingTask.objects.filter(
            oanda_account=account,
            status=TaskStatus.RUNNING,
        ).select_related("config")

        task_count = running_tasks.count()

        # Log periodically when there are running tasks (every 100 ticks per account)
        account_id = account.pk
        if account_id not in _task_log_counts:
            _task_log_counts[account_id] = 0
        _task_log_counts[account_id] += 1

        if task_count > 0:
            if _task_log_counts[account_id] % 100 == 1:  # Log on first tick and every 100
                task_names = [t.name for t in running_tasks]
                logger.info(
                    "Broadcasting tick to %d task(s) for account %s: %s",
                    task_count,
                    account.account_id,
                    task_names,
                )
        else:
            # Log "no running tasks" every 100 ticks
            if _task_log_counts[account_id] % 100 == 0:
                logger.info(
                    "No running trading tasks for account %s (id=%d) - %d ticks",
                    account.account_id,
                    account_id,
                    _task_log_counts[account_id],
                )

        for task in running_tasks:
            _process_tick_for_task(task, tick, tick_model, registry)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error broadcasting tick to trading tasks: %s", e, exc_info=True)

    # Also process tick through legacy Strategy objects (if any)
    try:
        active_strategies = Strategy.objects.filter(account=account, is_active=True)

        if not active_strategies.exists():
            return

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
                        strategy.pk,
                        len(orders),
                        tick.instrument,
                    )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error processing tick for strategy %s: %s", strategy.pk, e, exc_info=True
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
    time_limit=BACKTEST_HARD_TIME_LIMIT,
    soft_time_limit=BACKTEST_SOFT_TIME_LIMIT,
)
def run_backtest_task(  # type: ignore[no-untyped-def]
    self,  # pylint: disable=unused-argument
    task_id: int,
) -> Dict[str, Any]:
    """
    Execute a BacktestTask with resource limits.

    This task works with the BacktestTask model from the task-based
    strategy configuration feature.

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
            "Error in run_backtest_task for task_id=%d: %s",
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


@shared_task(
    soft_time_limit=STREAMING_TIME_LIMIT,
    time_limit=STREAMING_TIME_LIMIT + 3600,
)
def run_trading_task(task_id: int) -> Dict[str, Any]:
    """
    Execute a TradingTask.

    This task works with the TradingTask model from the task-based
    strategy configuration feature. Trading tasks run permanently until
    explicitly stopped, so time limits are disabled.

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
                result.get("oanda_account_id"),
            )

            # Start market data streaming for the account
            account_pk = result.get("account_id")  # Database PK
            instrument = result.get("instrument")

            if account_pk and instrument:
                # Trigger market data streaming
                stream_task = start_market_data_stream.delay(account_pk, instrument)
                logger.info(
                    "Started market data streaming for account %s "
                    "with instrument: %s (celery task: %s)",
                    result.get("oanda_account_id"),
                    instrument,
                    stream_task.id,
                )

                # Add log to execution
                from trading.execution_models import TaskExecution

                try:
                    execution = TaskExecution.objects.get(pk=result["execution_id"])
                    execution.add_log(
                        "INFO",
                        f"Market data stream started for {instrument} (task: {stream_task.id})",
                    )
                except TaskExecution.DoesNotExist:
                    pass
            else:
                logger.warning(
                    "TradingTask %d: Missing account_pk (%s) or instrument (%s) - "
                    "market data streaming not started",
                    task_id,
                    account_pk,
                    instrument,
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
            "Error in run_trading_task for task_id=%d: %s",
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
def stop_trading_task(task_id: int, stop_mode: str = "graceful") -> Dict[str, Any]:
    """
    Stop a running TradingTask with configurable stop mode.

    Args:
        task_id: Primary key of the TradingTask model instance
        stop_mode: Stop mode - 'immediate', 'graceful', or 'graceful_close'
            - immediate: Stop immediately without waiting
            - graceful: Stop gracefully, wait for pending operations (default)
            - graceful_close: Stop gracefully and close all open positions

    Returns:
        Dictionary containing success status and error message if any

    Requirements: 4.3, 7.2, 7.3
    """
    from trading.enums import StopMode
    from trading.services.task_executor import stop_trading_task_execution
    from trading.trading_task_models import TradingTask

    logger.info(
        "Stopping TradingTask for task_id=%d with mode=%s",
        task_id,
        stop_mode,
    )

    try:
        # Validate stop mode
        try:
            mode = StopMode(stop_mode)
        except ValueError:
            mode = StopMode.GRACEFUL
            logger.warning(
                "Invalid stop mode '%s', defaulting to '%s'",
                stop_mode,
                mode.value,
            )

        # Get the task to find the account
        task = TradingTask.objects.select_related("oanda_account").get(id=task_id)

        # Determine if we should close positions based on mode
        # graceful_close always closes, others respect sell_on_stop setting
        close_positions = mode == StopMode.GRACEFUL_CLOSE or task.sell_on_stop

        # Stop the task execution with the appropriate settings
        result = stop_trading_task_execution(
            task_id=task_id,
            close_positions=close_positions,
            immediate=mode == StopMode.IMMEDIATE,
        )

        if result["success"]:
            # Clear cached strategy instance
            if task_id in _strategy_instances:
                del _strategy_instances[task_id]
                logger.info("Cleared cached strategy instance for task %d", task_id)

            # Clear tick counters
            if task_id in _task_tick_counts:
                del _task_tick_counts[task_id]
            if task_id in _task_last_log_time:
                del _task_last_log_time[task_id]
            if task_id in _task_last_metrics_time:
                del _task_last_metrics_time[task_id]

            # Stop market data streaming for the account
            stop_market_data_stream.delay(task.oanda_account.pk)
            logger.info(
                "Stopped market data streaming for account %s",
                task.oanda_account.account_id,
            )

        # Add stop mode to result
        result["stop_mode"] = stop_mode

        return result

    except TradingTask.DoesNotExist:
        error_msg = f"TradingTask with id {task_id} does not exist"
        logger.error(error_msg)
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
            "stop_mode": stop_mode,
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to stop TradingTask: {str(e)}"
        logger.error(
            "Error in stop_trading_task for task_id=%d: %s",
            task_id,
            error_msg,
            exc_info=True,
        )
        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg,
            "stop_mode": stop_mode,
        }


@shared_task
def pause_trading_task(task_id: int) -> Dict[str, Any]:
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
            "Error in pause_trading_task for task_id=%d: %s",
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
def resume_trading_task(task_id: int) -> Dict[str, Any]:
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
            "Error in resume_trading_task for task_id=%d: %s",
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
def cleanup_stale_locks_task() -> Dict[str, Any]:
    """
    Clean up stale task locks that haven't received heartbeat updates.

    This task runs periodically (every 1 minute) to detect and clean up locks
    that are older than 5 minutes without a heartbeat update. This prevents
    orphaned locks from blocking task execution indefinitely.

    When a stale lock is detected:
    1. The lock is automatically released
    2. The associated task status is updated to "failed"
    3. An error message is recorded
    4. The cleanup action is logged for monitoring

    Returns:
        Dictionary containing:
            - success: Whether the cleanup completed successfully
            - cleaned_count: Number of stale locks cleaned up
            - failed_tasks: List of task IDs that were marked as failed
            - error: Error message if cleanup failed

    Requirements: 7.3, 7.4, 7.5
    """
    from trading.backtest_task_models import BacktestTask
    from trading.services.task_lock_manager import TaskLockManager

    logger.info("Starting stale lock cleanup task")

    try:
        lock_manager = TaskLockManager()
        cleaned_count = 0
        failed_tasks = []

        # Get all running backtest tasks
        running_tasks = BacktestTask.objects.filter(status=TaskStatus.RUNNING)

        logger.info("Checking %d running tasks for stale locks", running_tasks.count())

        for task in running_tasks:
            try:
                # Check if lock is stale
                was_stale = lock_manager.cleanup_stale_lock(
                    task_type="backtest",
                    task_id=task.pk,
                )

                if was_stale:
                    cleaned_count += 1
                    failed_tasks.append(task.pk)

                    # Update task status to failed
                    task.status = TaskStatus.FAILED
                    task.save(update_fields=["status", "updated_at"])

                    # Update latest execution status
                    latest_execution = task.get_latest_execution()
                    if latest_execution and latest_execution.status == TaskStatus.RUNNING:
                        latest_execution.status = TaskStatus.FAILED
                        latest_execution.error_message = (
                            "Task terminated due to stale lock (no heartbeat for >5 minutes)"
                        )
                        latest_execution.completed_at = timezone.now()
                        latest_execution.save(
                            update_fields=["status", "error_message", "completed_at"]
                        )

                    logger.warning(
                        "Cleaned up stale lock for task %d and marked as failed",
                        task.pk,
                    )

                    # Send WebSocket notification
                    from trading.services.notifications import send_task_status_notification

                    send_task_status_notification(
                        user_id=task.user.pk,
                        task_id=task.pk,
                        task_name=task.name,
                        task_type="backtest",
                        status=TaskStatus.FAILED,
                        execution_id=latest_execution.pk if latest_execution else None,
                        error_message=(
                            "Task terminated due to stale lock (no heartbeat for >5 minutes)"
                        ),
                    )

            except Exception as task_error:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error checking stale lock for task %d: %s",
                    task.pk,
                    task_error,
                    exc_info=True,
                )

        logger.info(
            "Stale lock cleanup completed: cleaned %d locks, failed %d tasks",
            cleaned_count,
            len(failed_tasks),
        )

        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "failed_tasks": failed_tasks,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Stale lock cleanup failed: {str(e)}"
        logger.error(
            "Error in cleanup_stale_locks_task: %s",
            error_msg,
            exc_info=True,
        )

        return {
            "success": False,
            "cleaned_count": 0,
            "failed_tasks": [],
            "error": error_msg,
        }


@shared_task
def resume_running_trading_tasks() -> Dict[str, Any]:
    """
    Resume all trading tasks that are marked as 'running' in the database.

    This task should be called on system startup (via Celery Beat or app ready signal)
    to ensure that trading tasks that were running before a restart are resumed
    with their market data streams.

    For each running task, this function:
    1. Checks if a market data stream is already running for the account
    2. If not, starts a new market data stream for the task's instrument
    3. Logs the action for monitoring

    Returns:
        Dictionary containing:
            - success: Whether the resume operation completed successfully
            - resumed_count: Number of tasks that had streams started
            - already_running: Number of tasks that already had streams
            - failed_tasks: List of task IDs that failed to resume
            - error: Error message if operation failed

    Requirements: 7.2, 7.3
    """
    from trading.trading_task_models import TradingTask

    logger.info("Checking for running trading tasks that need stream resumption...")

    try:
        # Find all tasks marked as running
        running_tasks = TradingTask.objects.filter(
            status=TaskStatus.RUNNING,
        ).select_related("oanda_account", "config")

        if not running_tasks.exists():
            logger.info("No running trading tasks found")
            return {
                "success": True,
                "resumed_count": 0,
                "already_running": 0,
                "failed_tasks": [],
                "error": None,
            }

        logger.info("Found %d running trading task(s)", running_tasks.count())

        resumed_count = 0
        already_running = 0
        failed_tasks = []

        for task in running_tasks:
            try:
                account = task.oanda_account
                instrument = task.config.parameters.get("instrument")

                if not instrument:
                    logger.warning(
                        "Task %d (%s) has no instrument configured, skipping",
                        task.pk,
                        task.name,
                    )
                    failed_tasks.append(task.pk)
                    continue

                # Check if stream is already running for this account
                cache_key = f"{STREAM_CACHE_PREFIX}{account.pk}"
                if cache.get(cache_key):
                    logger.info(
                        "Market data stream already running for task %d (%s) on account %s",
                        task.pk,
                        task.name,
                        account.account_id,
                    )
                    already_running += 1
                    continue

                # Start market data stream for this account
                logger.info(
                    "Starting market data stream for task %d (%s) on account %s, instrument %s",
                    task.pk,
                    task.name,
                    account.account_id,
                    instrument,
                )

                stream_task = start_market_data_stream.delay(account.pk, instrument)

                logger.info(
                    "Market data stream started for task %d (%s): celery_task=%s",
                    task.pk,
                    task.name,
                    stream_task.id,
                )

                resumed_count += 1

            except Exception as task_error:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to resume task %d (%s): %s",
                    task.pk,
                    task.name,
                    task_error,
                    exc_info=True,
                )
                failed_tasks.append(task.pk)

        logger.info(
            "Trading task resumption completed: resumed=%d, already_running=%d, failed=%d",
            resumed_count,
            already_running,
            len(failed_tasks),
        )

        return {
            "success": True,
            "resumed_count": resumed_count,
            "already_running": already_running,
            "failed_tasks": failed_tasks,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to resume running trading tasks: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            "success": False,
            "resumed_count": 0,
            "already_running": 0,
            "failed_tasks": [],
            "error": error_msg,
        }
