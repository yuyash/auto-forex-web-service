"""
Celery tasks for market data streaming and trading operations.

This module contains Celery tasks for:
- Starting and managing market data streams from OANDA
- Processing tick data and broadcasting to strategy executors
- Managing one stream per active OANDA account

Requirements: 7.1, 7.2, 12.1
"""

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
from trading.market_data_streamer import MarketDataStreamer, TickData
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
    instruments: list[str],
) -> Dict[str, Any]:
    # pylint: disable=too-many-locals,too-many-statements
    """
    Start market data streaming for an OANDA account.

    This task manages one stream per active OANDA account. It:
    - Initializes a MarketDataStreamer instance
    - Starts streaming for specified instruments
    - Processes ticks and broadcasts to strategy executor
    - Stores ticks to database (if enabled in configuration)
    - Handles reconnection on failures

    Args:
        account_id: Primary key of the OandaAccount
        instruments: List of currency pairs to stream (e.g., ['EUR_USD', 'GBP_USD'])

    Returns:
        Dictionary containing:
            - success: Whether the stream was started successfully
            - account_id: OANDA account ID
            - instruments: List of instruments being streamed
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
                "instruments": [],
                "error": error_msg,
            }

        # Check if account is active
        if not oanda_account.is_active:
            error_msg = f"Account {oanda_account.account_id} is not active"
            logger.warning(error_msg)
            return {
                "success": False,
                "account_id": oanda_account.account_id,
                "instruments": instruments,
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
                "instruments": instruments,
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
            3. Broadcast to strategy executor (TODO: implement in task 6.5)
            4. Broadcast to frontend via Django Channels (TODO: implement in task 5.4)

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

            # TODO: Task 6.5 - Broadcast to strategy executor  # pylint: disable=fixme
            # strategy_executor.process_tick(tick)

            # TODO: Task 5.4 - Broadcast to frontend via Django Channels  # pylint: disable=fixme
            # channel_layer = get_channel_layer()
            # async_to_sync(channel_layer.group_send)(
            #     f"market_data_{account_id}",
            #     {
            #         "type": "market_data_update",
            #         "data": tick.to_dict(),
            #     }
            # )

        streamer.register_tick_callback(on_tick)

        # Start the stream
        streamer.start_stream(instruments)

        # Mark stream as active in cache (expires after 1 hour)
        cache.set(cache_key, True, timeout=3600)

        logger.info(
            "Successfully started market data stream for account %s with instruments: %s",
            oanda_account.account_id,
            ", ".join(instruments),
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
            "instruments": instruments,
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
            "instruments": instruments,
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
