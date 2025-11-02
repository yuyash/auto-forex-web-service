"""
Celery tasks for market data streaming and trading operations.

This module contains Celery tasks for:
- Starting and managing market data streams from OANDA
- Processing tick data and broadcasting to strategy executors
- Managing one stream per active OANDA account

Requirements: 7.1, 7.2
"""

import logging
from typing import Any, Dict

from django.core.cache import cache

from celery import shared_task

from accounts.models import OandaAccount
from trading.market_data_streamer import MarketDataStreamer, TickData

logger = logging.getLogger(__name__)

# Cache key prefix for active streams
STREAM_CACHE_PREFIX = "market_data_stream:"


@shared_task(bind=True, max_retries=3)
def start_market_data_stream(  # type: ignore[no-untyped-def]  # pylint: disable=unused-argument
    self, account_id: int, instruments: list[str]
) -> Dict[str, Any]:
    """
    Start market data streaming for an OANDA account.

    This task manages one stream per active OANDA account. It:
    - Initializes a MarketDataStreamer instance
    - Starts streaming for specified instruments
    - Processes ticks and broadcasts to strategy executor
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

        # Create and initialize the market data streamer
        streamer = MarketDataStreamer(oanda_account)
        streamer.initialize_connection()

        # Register tick callback to process and broadcast ticks
        def on_tick(tick: TickData) -> None:
            """
            Process tick data and broadcast to strategy executor.

            This callback is called for each tick received from the stream.
            It will:
            1. Log the tick data
            2. Broadcast to strategy executor (TODO: implement in task 6.5)
            3. Broadcast to frontend via Django Channels (TODO: implement in task 5.4)

            Args:
                tick: Normalized tick data
            """
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

        return {
            "success": True,
            "account_id": oanda_account.account_id,
            "instruments": instruments,
            "error": None,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Failed to start market data stream: {str(e)}"
        logger.error(
            "Error starting market data stream for account %s: %s",
            account_id,
            error_msg,
            exc_info=True,
        )

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
