"""
Market Data Streaming Module

This module handles real-time market data streaming from OANDA v20 API.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

import v20

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class TickData:
    """Normalized tick data structure"""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        instrument: str,
        time: str,
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
        self.instruments: List[str] = []
        self.tick_callback: Optional[Callable[[TickData], None]] = None

    def initialize_connection(self) -> None:
        """
        Initialize the v20 API context.

        Raises:
            ValueError: If account API credentials are invalid
        """
        if not self.account.api_token:
            raise ValueError("API token is required for streaming")

        # Determine API hostname based on account type
        if self.account.api_type == "practice":
            hostname = "api-fxpractice.oanda.com"
        elif self.account.api_type == "live":
            hostname = "api-fxtrade.oanda.com"
        else:
            raise ValueError(f"Invalid API type: {self.account.api_type}")

        # Create v20 context
        self.api_context = v20.Context(
            hostname=hostname,
            token=self.account.api_token,
            port=443,
            ssl=True,
            application="AutoForexTradingSystem",
        )

        logger.info(
            "Initialized v20 context for account %s (%s)",
            self.account.account_id,
            self.account.api_type,
        )

    def start_stream(self, instruments: List[str]) -> None:
        """
        Start streaming market data for specified instruments.

        Args:
            instruments: List of currency pairs (e.g., ['EUR_USD', 'GBP_USD'])

        Raises:
            RuntimeError: If connection is not initialized
            v20.V20Error: If stream connection fails
        """
        if not self.api_context:
            raise RuntimeError("Connection not initialized. Call initialize_connection() first.")

        if not instruments:
            raise ValueError("At least one instrument is required")

        self.instruments = instruments

        try:
            # Create pricing stream
            response = self.api_context.pricing.stream(
                accountID=self.account.account_id, instruments=",".join(instruments), snapshot=True
            )

            self.stream = response
            self.is_connected = True

            logger.info(
                "Started market data stream for account %s, instruments: %s",
                self.account.account_id,
                ", ".join(instruments),
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to start market data stream: %s", e)
            self.is_connected = False
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

    def _process_heartbeat_message(self, heartbeat_msg: Any) -> None:
        """
        Process a heartbeat message to monitor connection health.

        Args:
            heartbeat_msg: Heartbeat message from v20 stream
        """
        logger.debug("Received heartbeat at %s", heartbeat_msg.time)

    def register_tick_callback(self, callback: Callable[[TickData], None]) -> None:
        """
        Register a callback function to be called on each tick.

        Args:
            callback: Function that takes a TickData object as parameter
        """
        self.tick_callback = callback
        logger.info("Registered tick callback")

    def stop_stream(self) -> None:
        """
        Stop the market data stream and clean up resources.
        """
        if self.stream:
            try:
                # Close the stream
                self.stream.terminate("User requested stop")
                logger.info("Stopped market data stream for account %s", self.account.account_id)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error stopping stream: %s", e)
            finally:
                self.stream = None
                self.is_connected = False

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get the current connection status.

        Returns:
            Dictionary with connection status information
        """
        return {
            "is_connected": self.is_connected,
            "account_id": self.account.account_id,
            "instruments": self.instruments,
            "api_type": self.account.api_type,
        }
