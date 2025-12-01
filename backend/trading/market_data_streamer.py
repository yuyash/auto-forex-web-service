"""
Market Data Streaming Module

This module handles real-time market data streaming from OANDA v20 API.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import v20
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class ReconnectionManager:
    """
    Manages reconnection logic with exponential backoff.

    This class implements:
    - Exponential backoff intervals (1s, 2s, 4s, 8s, 16s)
    - Maximum 5 retry attempts
    - Connection failure logging
    - Reconnection attempt tracking
    """

    def __init__(self, max_attempts: int = 5):
        """
        Initialize the reconnection manager.

        Args:
            max_attempts: Maximum number of reconnection attempts (default: 5)
        """
        self.max_attempts = max_attempts
        self.current_attempt = 0
        self.backoff_intervals = [1, 2, 4, 8, 16]  # seconds

    def should_retry(self) -> bool:
        """
        Check if another retry attempt should be made.

        Returns:
            True if retry attempts remain, False otherwise
        """
        return self.current_attempt < self.max_attempts

    def get_backoff_interval(self) -> float:
        """
        Get the backoff interval for the current attempt.

        Returns:
            Backoff interval in seconds
        """
        if self.current_attempt < len(self.backoff_intervals):
            return self.backoff_intervals[self.current_attempt]
        # If we exceed predefined intervals, use the last one
        return self.backoff_intervals[-1]

    def wait_before_retry(self) -> None:
        """
        Wait for the appropriate backoff interval before retrying.

        This method blocks for the duration of the backoff interval.
        """
        interval = self.get_backoff_interval()
        logger.info(
            "Waiting %s seconds before retry attempt %d/%d",
            interval,
            self.current_attempt + 1,
            self.max_attempts,
        )
        time.sleep(interval)

    def record_attempt(self) -> None:
        """
        Record a reconnection attempt.

        This increments the attempt counter.
        """
        self.current_attempt += 1
        logger.info("Reconnection attempt %d/%d", self.current_attempt, self.max_attempts)

    def reset(self) -> None:
        """
        Reset the reconnection manager after a successful connection.

        This resets the attempt counter to 0.
        """
        logger.info("Connection successful, resetting reconnection manager")
        self.current_attempt = 0

    def log_failure(self, error: Exception) -> None:
        """
        Log a connection failure.

        Args:
            error: The exception that caused the failure
        """
        logger.error(
            "Connection attempt %d/%d failed: %s",
            self.current_attempt,
            self.max_attempts,
            str(error),
        )

    def log_max_attempts_reached(self) -> None:
        """
        Log that maximum retry attempts have been reached.
        """
        logger.error("Maximum reconnection attempts (%d) reached. Giving up.", self.max_attempts)

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the reconnection manager.

        Returns:
            Dictionary with status information
        """
        return {
            "current_attempt": self.current_attempt,
            "max_attempts": self.max_attempts,
            "can_retry": self.should_retry(),
            "next_backoff_interval": self.get_backoff_interval() if self.should_retry() else None,
        }


class TickData:
    """Normalized tick data structure"""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        instrument: str,
        time: str,  # pylint: disable=redefined-outer-name
        bid: float,
        ask: float,
        bid_liquidity: Optional[int] = None,
        ask_liquidity: Optional[int] = None,
    ):
        self.instrument = instrument
        self.time = time
        self.bid = bid
        self.ask = ask
        self.mid = (bid + ask) / 2
        self.spread = ask - bid
        self.bid_liquidity = bid_liquidity
        self.ask_liquidity = ask_liquidity

    def to_dict(self) -> Dict[str, Any]:
        """Convert tick data to dictionary"""
        return {
            "instrument": self.instrument,
            "time": self.time,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread": self.spread,
            "bid_liquidity": self.bid_liquidity,
            "ask_liquidity": self.ask_liquidity,
        }


class MarketDataStreamer:
    """
    Manages real-time market data streaming from OANDA v20 API.

    This class handles:
    - v20 pricing stream connection
    - Stream initialization and connection management
    - Tick data processing and normalization
    - Connection health monitoring
    """

    def __init__(self, account: OandaAccount):
        """
        Initialize the market data streamer.

        Args:
            account: OandaAccount instance with API credentials
        """
        self.account = account
        self.api_context: Optional[v20.Context] = None
        self.stream: Optional[Any] = None
        self.is_connected = False
        self.instrument: str | None = None
        self.tick_callback: Optional[Callable[[TickData], None]] = None
        self.reconnection_manager = ReconnectionManager(max_attempts=5)

    def initialize_connection(self) -> None:
        """
        Initialize the v20 API context for streaming.

        Note: OANDA requires different hostnames for REST API vs streaming:
        - REST API: api-fxpractice.oanda.com / api-fxtrade.oanda.com
        - Streaming: stream-fxpractice.oanda.com / stream-fxtrade.oanda.com

        Raises:
            ValueError: If account API credentials are invalid
        """
        if not self.account.get_api_token():
            raise ValueError("API token is required for streaming")

        # Determine streaming hostname based on account type
        # IMPORTANT: Use stream-* hostname for pricing streams, not api-*
        if self.account.api_type == "practice":
            hostname = "stream-fxpractice.oanda.com"
        elif self.account.api_type == "live":
            hostname = "stream-fxtrade.oanda.com"
        else:
            raise ValueError(f"Invalid API type: {self.account.api_type}")

        # Create v20 context for streaming
        # Note: api_token is encrypted, use get_api_token() to decrypt
        self.api_context = v20.Context(
            hostname=hostname,
            token=self.account.get_api_token(),
            port=443,
            ssl=True,
            application="AutoForexTradingSystem",
        )

        logger.info(
            "Initialized v20 context for account %s (%s)",
            self.account.account_id,
            self.account.api_type,
        )

    def start_stream(self, instrument: str) -> None:
        """
        Start streaming market data for specified instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')

        Raises:
            RuntimeError: If connection is not initialized
            v20.V20Error: If stream connection fails
        """
        if not self.api_context:
            raise RuntimeError("Connection not initialized. Call initialize_connection() first.")

        if not instrument:
            raise ValueError("Instrument is required")

        self.instrument = instrument

        try:
            # Create pricing stream
            response = self.api_context.pricing.stream(
                accountID=self.account.account_id, instruments=instrument, snapshot=True
            )

            self.stream = response
            self.is_connected = True
            # Reset reconnection manager on successful connection
            self.reconnection_manager.reset()

            logger.info(
                "Started market data stream for account %s, instrument: %s",
                self.account.account_id,
                instrument,
            )

            # Broadcast connection status
            self._broadcast_connection_status("connected", "Stream connected successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to start market data stream: %s", e)
            self.is_connected = False
            # Broadcast error status
            self._broadcast_connection_status("error", f"Failed to connect: {str(e)}")
            raise

    def process_stream(self) -> None:
        """
        Process incoming tick data from the stream.

        This method continuously reads from the stream and processes each message.
        It should be run in a separate thread or async task.

        Raises:
            RuntimeError: If stream is not started
        """
        if not self.stream:
            raise RuntimeError("Stream not started. Call start_stream() first.")

        logger.info("Processing market data stream for account %s", self.account.account_id)

        try:
            for msg_type, msg in self.stream.parts():
                if msg_type == "pricing.Price":
                    self._process_price_message(msg)
                elif msg_type == "pricing.Heartbeat":
                    self._process_heartbeat_message(msg)
                else:
                    logger.debug("Received unknown message type: %s", msg_type)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing stream: %s", e)
            self.is_connected = False
            raise

    def _process_price_message(self, price_msg: Any) -> None:
        """
        Process a price message and normalize tick data.

        Args:
            price_msg: Price message from v20 stream
        """
        try:
            # Extract price data
            instrument = price_msg.instrument
            time_str = price_msg.time

            # Get bid and ask prices
            bids = price_msg.bids
            asks = price_msg.asks

            if not bids or not asks:
                logger.warning("Missing bid/ask data for %s", instrument)
                return

            # Use the first bid/ask (most liquid)
            bid_price = float(bids[0].price)
            ask_price = float(asks[0].price)
            bid_liquidity = bids[0].liquidity if hasattr(bids[0], "liquidity") else None
            ask_liquidity = asks[0].liquidity if hasattr(asks[0], "liquidity") else None

            # Create normalized tick data
            tick = TickData(
                instrument=instrument,
                time=time_str,
                bid=bid_price,
                ask=ask_price,
                bid_liquidity=bid_liquidity,
                ask_liquidity=ask_liquidity,
            )

            # Update P&L for open positions with this instrument
            self._update_positions_pnl(tick)

            # Broadcast tick data to WebSocket consumers
            self._broadcast_tick_to_websocket(tick)

            # Call tick callback if registered
            if self.tick_callback:
                self.tick_callback(tick)

            logger.debug(
                "Processed tick: %s @ %s, bid=%s, ask=%s, mid=%s",
                instrument,
                time_str,
                bid_price,
                ask_price,
                tick.mid,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing price message: %s", e)

    def _update_positions_pnl(self, tick: TickData) -> None:
        """
        Update unrealized P&L for open positions with this instrument.

        This method:
        - Fetches all open positions for this account and instrument
        - Calculates unrealized P&L based on current market price
        - Updates Position.unrealized_pnl and Position.current_price
        - Broadcasts P&L updates via WebSocket

        Args:
            tick: Normalized tick data with current prices

        Requirements: 9.1, 9.4
        """
        try:
            from decimal import Decimal  # pylint: disable=import-outside-toplevel

            from .models import Position  # pylint: disable=import-outside-toplevel

            # Get all open positions for this account and instrument
            open_positions = Position.objects.filter(
                account=self.account, instrument=tick.instrument, closed_at__isnull=True
            )

            if not open_positions.exists():
                return

            # Determine the appropriate price for P&L calculation
            # For long positions, use bid (exit price)
            # For short positions, use ask (exit price)
            positions_updated = []

            for position in open_positions:
                # Use bid for long positions (selling), ask for short positions (buying back)
                current_price = Decimal(str(tick.bid if position.direction == "long" else tick.ask))

                # Calculate unrealized P&L
                old_pnl = position.unrealized_pnl
                position.calculate_unrealized_pnl(current_price)

                # Only update if P&L changed significantly (avoid unnecessary DB writes)
                if abs(position.unrealized_pnl - old_pnl) >= Decimal("0.01"):
                    position.save(update_fields=["current_price", "unrealized_pnl"])
                    positions_updated.append(
                        {
                            "position_id": position.position_id,
                            "instrument": position.instrument,
                            "direction": position.direction,
                            "units": str(position.units),
                            "entry_price": str(position.entry_price),
                            "current_price": str(position.current_price),
                            "unrealized_pnl": str(position.unrealized_pnl),
                        }
                    )

            # Broadcast P&L updates if any positions were updated
            if positions_updated:
                self._broadcast_pnl_updates(positions_updated)

                logger.debug(
                    "Updated P&L for %d positions on %s", len(positions_updated), tick.instrument
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error updating positions P&L: %s", e)

    def _broadcast_pnl_updates(self, positions: List[Dict[str, Any]]) -> None:
        """
        Broadcast P&L updates to WebSocket consumers via Django Channels.

        This method sends position P&L updates to the channel layer, which then
        broadcasts them to all connected WebSocket clients for this account.

        Args:
            positions: List of position data dictionaries with updated P&L

        Requirements: 9.4
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured, skipping P&L broadcast")
                return

            # Create group name for this account
            group_name = f"market_data_{self.account.id}"

            # Send message to the group
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "pnl_update",
                    "data": {
                        "positions": positions,
                        "account_id": self.account.account_id,
                    },
                },
            )

            logger.debug("Broadcasted P&L updates to WebSocket group: %s", group_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error broadcasting P&L updates to WebSocket: %s", e)

    def _broadcast_tick_to_websocket(self, tick: TickData) -> None:
        """
        Broadcast tick data to WebSocket consumers via Django Channels.

        This method sends the tick data to the channel layer, which then
        broadcasts it to all connected WebSocket clients for this account and instrument.

        Args:
            tick: Normalized tick data to broadcast
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured, skipping WebSocket broadcast")
                return

            # Create group name for this account and instrument
            group_name = f"market_data_{self.account.id}_{tick.instrument}"

            # Send message to the group
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "market_data_update",
                    "data": tick.to_dict(),
                },
            )

            logger.debug("Broadcasted tick to WebSocket group: %s", group_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error broadcasting tick to WebSocket: %s", e)

    def _process_heartbeat_message(self, heartbeat_msg: Any) -> None:
        """
        Process a heartbeat message to monitor connection health.

        Args:
            heartbeat_msg: Heartbeat message from v20 stream
        """
        heartbeat_time = heartbeat_msg.time
        logger.debug("Received heartbeat at %s", heartbeat_time)

    def register_tick_callback(self, callback: Callable[[TickData], None]) -> None:
        """
        Register a callback function to be called on each tick.

        Args:
            callback: Function that takes a TickData object as parameter
        """
        self.tick_callback = callback
        logger.info("Registered tick callback")

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to the market data stream with exponential backoff.

        This method will retry up to max_attempts times with exponential backoff
        intervals (1s, 2s, 4s, 8s, 16s).

        Returns:
            True if reconnection was successful, False otherwise
        """
        if not self.instrument:
            logger.error("Cannot reconnect: no instrument configured")
            return False

        logger.info("Starting reconnection process for account %s", self.account.account_id)

        # Broadcast reconnecting status
        self._broadcast_connection_status("reconnecting", "Attempting to reconnect...")

        while self.reconnection_manager.should_retry():
            try:
                # Wait before attempting reconnection
                self.reconnection_manager.wait_before_retry()

                # Record the attempt
                self.reconnection_manager.record_attempt()

                # Attempt to start the stream
                self.start_stream(self.instrument)

                # If we get here, connection was successful
                logger.info(
                    "Successfully reconnected to market data stream for account %s",
                    self.account.account_id,
                )
                return True

            except Exception as e:  # pylint: disable=broad-exception-caught
                # Log the failure
                self.reconnection_manager.log_failure(e)

                # Check if we should continue retrying
                if not self.reconnection_manager.should_retry():
                    self.reconnection_manager.log_max_attempts_reached()
                    # Broadcast final failure
                    max_attempts = self.reconnection_manager.max_attempts
                    self._broadcast_connection_status(
                        "error", f"Failed to reconnect after {max_attempts} attempts"
                    )
                    return False

        # If we exit the loop without success
        self.reconnection_manager.log_max_attempts_reached()
        max_attempts = self.reconnection_manager.max_attempts
        self._broadcast_connection_status(
            "error", f"Failed to reconnect after {max_attempts} attempts"
        )
        return False

    def stop_stream(self) -> None:
        """
        Stop the market data stream and clean up resources.
        """
        if self.stream:
            try:
                # Close the stream
                self.stream.terminate("User requested stop")
                logger.info("Stopped market data stream for account %s", self.account.account_id)

                # Broadcast disconnection status
                self._broadcast_connection_status("disconnected", "Stream stopped by user")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error stopping stream: %s", e)
            finally:
                self.stream = None
                self.is_connected = False

    def _broadcast_connection_status(self, status: str, message: str = "") -> None:
        """
        Broadcast connection status updates to WebSocket consumers.

        Args:
            status: Connection status (connected, disconnected, reconnecting, error)
            message: Optional status message
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            group_name = f"market_data_{self.account.id}"

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "connection_status",
                    "data": {
                        "status": status,
                        "message": message,
                        "account_id": self.account.account_id,
                        "is_connected": self.is_connected,
                    },
                },
            )

            logger.debug(
                "Broadcasted connection status '%s' to WebSocket group: %s", status, group_name
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error broadcasting connection status: %s", e)

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get the current connection status.

        Returns:
            Dictionary with connection status information
        """
        return {
            "is_connected": self.is_connected,
            "account_id": self.account.account_id,
            "instrument": self.instrument,
            "api_type": self.account.api_type,
            "reconnection_status": self.reconnection_manager.get_status(),
        }
