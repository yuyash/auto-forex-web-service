"""
Transaction Streaming Module

This module handles real-time transaction streaming from OANDA v20 API
to synchronize order fills, cancellations, and position changes.

Requirements: 8.3, 9.1, 9.5
"""

import logging
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from django.utils import timezone

import v20
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import OandaAccount
from trading.event_models import Event
from trading.models import Order, Position

logger = logging.getLogger(__name__)


class TransactionData:
    """Normalized transaction data structure"""

    # pylint: disable=too-many-arguments,too-many-positional-arguments,redefined-outer-name
    def __init__(
        self,
        transaction_id: str,
        transaction_type: str,
        time: str,
        account_id: str,
        details: Dict[str, Any],
    ):
        self.transaction_id = transaction_id
        self.transaction_type = transaction_type
        self.time = time
        self.account_id = account_id
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction data to dictionary"""
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type,
            "time": self.time,
            "account_id": self.account_id,
            "details": self.details,
        }


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


class TransactionStreamer:
    """
    Manages real-time transaction streaming from OANDA v20 API.

    This class handles:
    - v20 transaction stream connection
    - Transaction processing for order fills, cancellations, and position changes
    - Connection health monitoring
    - Automatic reconnection with exponential backoff

    Requirements: 8.3, 9.1, 9.5
    """

    def __init__(self, account: OandaAccount):
        """
        Initialize the transaction streamer.

        Args:
            account: OandaAccount instance with API credentials
        """
        self.account = account
        self.api_context: Optional[v20.Context] = None
        self.stream: Optional[Any] = None
        self.is_connected = False
        self.transaction_callback: Optional[Callable[[TransactionData], None]] = None
        self.reconnection_manager = ReconnectionManager(max_attempts=5)

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
            "Initialized v20 context for transaction stream, account %s (%s)",
            self.account.account_id,
            self.account.api_type,
        )

    def start_stream(self) -> None:
        """
        Start streaming transactions from OANDA.

        Raises:
            RuntimeError: If connection is not initialized
            v20.V20Error: If stream connection fails
        """
        if not self.api_context:
            raise RuntimeError("Connection not initialized. Call initialize_connection() first.")

        try:
            # Create transaction stream
            response = self.api_context.transaction.stream(accountID=self.account.account_id)

            self.stream = response
            self.is_connected = True
            # Reset reconnection manager on successful connection
            self.reconnection_manager.reset()

            logger.info(
                "Started transaction stream for account %s",
                self.account.account_id,
            )

            # Log system event
            Event.log_system_event(
                event_type="transaction_stream_started",
                description=f"Transaction stream started for account {self.account.account_id}",
                severity="info",
                details={
                    "account_id": self.account.account_id,
                    "api_type": self.account.api_type,
                },
            )

            # Broadcast connection status
            self._broadcast_connection_status("connected", "Transaction stream connected")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to start transaction stream: %s", e)
            self.is_connected = False
            # Broadcast error status
            self._broadcast_connection_status("error", f"Failed to connect: {str(e)}")
            raise

    def process_stream(self) -> None:
        """
        Process incoming transactions from the stream.

        This method continuously reads from the stream and processes each transaction.
        It should be run in a separate thread or async task.

        Raises:
            RuntimeError: If stream is not started
        """
        if not self.stream:
            raise RuntimeError("Stream not started. Call start_stream() first.")

        logger.info("Processing transaction stream for account %s", self.account.account_id)

        try:
            for msg_type, msg in self.stream.parts():
                if msg_type == "transaction.Transaction":
                    self._process_transaction_message(msg)
                elif msg_type == "transaction.Heartbeat":
                    self._process_heartbeat_message(msg)
                else:
                    logger.debug("Received unknown message type: %s", msg_type)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing transaction stream: %s", e)
            self.is_connected = False
            raise

    def _process_transaction_message(self, transaction_msg: Any) -> None:
        """
        Process a transaction message and route to appropriate handler.

        Args:
            transaction_msg: Transaction message from v20 stream
        """
        try:
            # Extract transaction data
            transaction_id = transaction_msg.id
            transaction_type = transaction_msg.type
            time_str = transaction_msg.time

            logger.debug(
                "Processing transaction: %s (type: %s)",
                transaction_id,
                transaction_type,
            )

            # Create normalized transaction data
            transaction = TransactionData(
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                time=time_str,
                account_id=self.account.account_id,
                details=transaction_msg.dict(),
            )

            # Route to appropriate handler based on transaction type
            if transaction_type == "ORDER_FILL":
                self._handle_order_fill(transaction)
            elif transaction_type == "ORDER_CANCEL":
                self._handle_order_cancel(transaction)
            elif transaction_type in [
                "MARKET_ORDER_REJECT",
                "LIMIT_ORDER_REJECT",
                "STOP_ORDER_REJECT",
            ]:
                self._handle_order_reject(transaction)
            elif transaction_type in ["TRADE_CLOSE", "TRADE_REDUCE"]:
                self._handle_position_update(transaction)
            else:
                logger.debug("Unhandled transaction type: %s", transaction_type)

            # Call transaction callback if registered
            if self.transaction_callback:
                self.transaction_callback(transaction)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing transaction message: %s", e)

    def _handle_order_fill(self, transaction: TransactionData) -> None:
        """
        Handle ORDER_FILL transaction.

        Updates Order status to 'filled' and creates/updates Position record.

        Args:
            transaction: Transaction data

        Requirements: 8.3, 9.1
        """
        try:
            details = transaction.details
            order_id = details.get("orderID")
            instrument = details.get("instrument")
            units = Decimal(str(details.get("units", 0)))
            price = Decimal(str(details.get("price", 0)))
            pl = Decimal(str(details.get("pl", 0)))

            logger.info(
                "Order fill detected: order_id=%s, instrument=%s, units=%s, price=%s",
                order_id,
                instrument,
                units,
                price,
            )

            # Update Order status
            try:
                order = Order.objects.get(order_id=order_id, account=self.account)
                order.status = "filled"
                order.filled_at = timezone.now()
                order.save(update_fields=["status", "filled_at"])

                logger.info("Updated order %s status to filled", order_id)

                # Create or update Position
                self._create_or_update_position(order, price, units)

            except Order.DoesNotExist:
                logger.warning("Order %s not found in database for fill event", order_id)

            # Log order fill event
            Event.log_trading_event(
                event_type="order_filled",
                description=f"Order filled: {instrument} {units} units @ {price}",
                severity="info",
                user=self.account.user,
                account=self.account,
                details={
                    "transaction_id": transaction.transaction_id,
                    "order_id": order_id,
                    "instrument": instrument,
                    "units": str(units),
                    "price": str(price),
                    "pl": str(pl),
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error handling order fill: %s", e)

    def _handle_order_cancel(self, transaction: TransactionData) -> None:
        """
        Handle ORDER_CANCEL transaction.

        Updates Order status to 'cancelled'.

        Args:
            transaction: Transaction data

        Requirements: 8.2
        """
        try:
            details = transaction.details
            order_id = details.get("orderID")

            logger.info("Order cancel detected: order_id=%s", order_id)

            # Update Order status
            try:
                order = Order.objects.get(order_id=order_id, account=self.account)
                order.status = "cancelled"
                order.save(update_fields=["status"])

                logger.info("Updated order %s status to cancelled", order_id)

            except Order.DoesNotExist:
                logger.warning("Order %s not found in database for cancel event", order_id)

            # Log order cancellation event
            Event.log_trading_event(
                event_type="order_cancelled",
                description=f"Order cancelled: {order_id}",
                severity="info",
                user=self.account.user,
                account=self.account,
                details={
                    "transaction_id": transaction.transaction_id,
                    "order_id": order_id,
                    "reason": details.get("reason", "Unknown"),
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error handling order cancel: %s", e)

    def _handle_order_reject(self, transaction: TransactionData) -> None:
        """
        Handle order rejection transactions.

        Updates Order status to 'rejected'.

        Args:
            transaction: Transaction data
        """
        try:
            details = transaction.details
            order_id = details.get("orderID")
            reject_reason = details.get("rejectReason", "Unknown")

            logger.warning("Order reject detected: order_id=%s, reason=%s", order_id, reject_reason)

            # Update Order status
            try:
                order = Order.objects.get(order_id=order_id, account=self.account)
                order.status = "rejected"
                order.save(update_fields=["status"])

                logger.info("Updated order %s status to rejected", order_id)

            except Order.DoesNotExist:
                logger.warning("Order %s not found in database for reject event", order_id)

            # Log order rejection event
            Event.log_trading_event(
                event_type="order_rejected",
                description=f"Order rejected: {order_id} - {reject_reason}",
                severity="warning",
                user=self.account.user,
                account=self.account,
                details={
                    "transaction_id": transaction.transaction_id,
                    "order_id": order_id,
                    "reject_reason": reject_reason,
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error handling order reject: %s", e)

    def _handle_position_update(self, transaction: TransactionData) -> None:
        """
        Handle position update transactions (TRADE_CLOSE, TRADE_REDUCE).

        Updates Position records with current state and calculates realized P&L.

        Args:
            transaction: Transaction data

        Requirements: 9.1, 9.5
        """
        try:
            details = transaction.details
            trade_id = details.get("tradeID")
            instrument = details.get("instrument")
            units = Decimal(str(details.get("units", 0)))
            price = Decimal(str(details.get("price", 0)))
            pl = Decimal(str(details.get("pl", 0)))
            transaction_type = transaction.transaction_type

            logger.info(
                "Position update detected: type=%s, trade_id=%s, instrument=%s, units=%s, price=%s",
                transaction_type,
                trade_id,
                instrument,
                units,
                price,
            )

            # Find position by trade ID or instrument
            try:
                position = Position.objects.get(
                    position_id=trade_id,
                    account=self.account,
                    closed_at__isnull=True,
                )

                if transaction_type == "TRADE_CLOSE":
                    # Close the position
                    position.realized_pnl = pl
                    position.closed_at = timezone.now()
                    position.current_price = price
                    position.save(update_fields=["realized_pnl", "closed_at", "current_price"])

                    logger.info("Closed position %s with P&L: %s", trade_id, pl)

                    # Log position close event
                    description = (
                        f"Position closed: {instrument} {units} units @ {price}, " f"P&L: {pl}"
                    )
                    Event.log_trading_event(
                        event_type="position_closed",
                        description=description,
                        severity="info",
                        user=self.account.user,
                        account=self.account,
                        details={
                            "transaction_id": transaction.transaction_id,
                            "trade_id": trade_id,
                            "instrument": instrument,
                            "units": str(units),
                            "price": str(price),
                            "pl": str(pl),
                        },
                    )

                elif transaction_type == "TRADE_REDUCE":
                    # Partial close - update units
                    position.units = abs(units)
                    position.current_price = price
                    position.save(update_fields=["units", "current_price"])

                    logger.info("Reduced position %s to %s units", trade_id, abs(units))

                    # Log position reduce event
                    description = (
                        f"Position reduced: {instrument} to {abs(units)} units " f"@ {price}"
                    )
                    Event.log_trading_event(
                        event_type="position_reduced",
                        description=description,
                        severity="info",
                        user=self.account.user,
                        account=self.account,
                        details={
                            "transaction_id": transaction.transaction_id,
                            "trade_id": trade_id,
                            "instrument": instrument,
                            "units": str(abs(units)),
                            "price": str(price),
                            "pl": str(pl),
                        },
                    )

            except Position.DoesNotExist:
                logger.warning("Position %s not found in database for update", trade_id)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error handling position update: %s", e)

    def _create_or_update_position(self, order: Order, fill_price: Decimal, units: Decimal) -> None:
        """
        Create or update Position record on order fill.

        Args:
            order: Filled order
            fill_price: Fill price
            units: Number of units
        """
        try:
            # Check if position already exists for this instrument
            existing_position = Position.objects.filter(
                account=self.account,
                instrument=order.instrument,
                direction=order.direction,
                closed_at__isnull=True,
            ).first()

            if existing_position:
                # Update existing position (add to it)
                existing_position.units += abs(units)
                existing_position.current_price = fill_price
                existing_position.save(update_fields=["units", "current_price"])

                logger.info(
                    "Updated existing position %s, new units: %s",
                    existing_position.position_id,
                    existing_position.units,
                )
            else:
                # Create new position
                position = Position.objects.create(
                    account=self.account,
                    strategy=order.strategy,
                    position_id=order.order_id,  # Use order ID as position ID initially
                    instrument=order.instrument,
                    direction=order.direction,
                    units=abs(units),
                    entry_price=fill_price,
                    current_price=fill_price,
                    unrealized_pnl=Decimal("0"),
                )

                logger.info(
                    "Created new position %s: %s %s units @ %s",
                    position.position_id,
                    position.direction,
                    position.units,
                    position.entry_price,
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error creating/updating position: %s", e)

    def _process_heartbeat_message(self, heartbeat_msg: Any) -> None:
        """
        Process a heartbeat message to monitor connection health.

        Args:
            heartbeat_msg: Heartbeat message from v20 stream
        """
        heartbeat_time = heartbeat_msg.time
        logger.debug("Received transaction stream heartbeat at %s", heartbeat_time)

    def register_transaction_callback(self, callback: Callable[[TransactionData], None]) -> None:
        """
        Register a callback function to be called on each transaction.

        Args:
            callback: Function that takes a TransactionData object as parameter
        """
        self.transaction_callback = callback
        logger.info("Registered transaction callback")

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to the transaction stream with exponential backoff.

        This method will retry up to max_attempts times with exponential backoff
        intervals (1s, 2s, 4s, 8s, 16s).

        Returns:
            True if reconnection was successful, False otherwise
        """
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
                self.start_stream()

                # If we get here, connection was successful
                logger.info(
                    "Successfully reconnected to transaction stream for account %s",
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
        Stop the transaction stream and clean up resources.
        """
        if self.stream:
            try:
                # Close the stream
                self.stream.terminate("User requested stop")
                logger.info("Stopped transaction stream for account %s", self.account.account_id)

                # Log system event
                Event.log_system_event(
                    event_type="transaction_stream_stopped",
                    description=f"Transaction stream stopped for account {self.account.account_id}",
                    severity="info",
                    details={
                        "account_id": self.account.account_id,
                    },
                )

                # Broadcast disconnection status
                self._broadcast_connection_status("disconnected", "Stream stopped by user")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error stopping transaction stream: %s", e)
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

            group_name = f"transaction_stream_{self.account.id}"

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
                "Broadcasted transaction stream status '%s' to WebSocket group: %s",
                status,
                group_name,
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
            "api_type": self.account.api_type,
            "reconnection_status": self.reconnection_manager.get_status(),
        }
