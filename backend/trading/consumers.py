"""
WebSocket consumers for real-time market data streaming.

This module implements Django Channels consumers for broadcasting
real-time market data updates to connected frontend clients.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any, Dict, List, Optional

from django.core.exceptions import ObjectDoesNotExist

from channels.generic.websocket import AsyncWebsocketConsumer

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class MarketDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming market data to frontend clients.

    This consumer:
    - Accepts WebSocket connections from authenticated users
    - Subscribes to market data updates for a specific OANDA account or "default" demo mode
    - Broadcasts tick updates to connected clients
    - Implements message batching for performance optimization
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/market-data/<account_id>/<instrument>/
    - account_id: OANDA account ID or "default" for demo mode
    - instrument: Currency pair (e.g., "USD_JPY", "EUR_USD")

    Requirements: 7.3
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer with batching configuration."""
        super().__init__(*args, **kwargs)
        self.account_id: Optional[str] = None
        self.instrument: str = "USD_JPY"  # Default instrument
        self.group_name: Optional[str] = None
        self.user = None

        # Message batching configuration
        self.batch_size = 10  # Maximum messages per batch
        self.batch_interval = 0.1  # Maximum time to wait before sending batch (100ms)
        self.message_buffer: List[Dict[str, Any]] = []
        self.batch_task: Optional[asyncio.Task] = None
        self.is_batching = True

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Validates account ownership (or allows "default" for demo mode)
        3. Joins the account-specific channel group
        4. Accepts the WebSocket connection
        5. Starts the message batching task
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt")
            await self.close(code=4001)
            return

        # Get account ID and instrument from URL route
        self.account_id = self.scope["url_route"]["kwargs"]["account_id"]
        self.instrument = self.scope["url_route"]["kwargs"].get("instrument", "USD_JPY")

        # Handle "default" account case (no OANDA account configured)
        if self.account_id == "default":
            # Create a demo/default group name
            self.group_name = f"market_data_default_{self.user.id}_{self.instrument}"

            # Join the channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

            # Send warning message about demo mode
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "demo_warning",
                        "data": {
                            "message": "You are viewing simulated demo data. "
                            "Please register an OANDA account to view real market data.",
                            "severity": "warning",
                            "is_demo": True,
                            "instrument": self.instrument,
                        },
                    }
                )
            )

            # Start the batching task
            if self.is_batching:
                self.batch_task = asyncio.create_task(self._batch_sender())

            # Start demo market data stream
            try:
                from .demo_market_data import (  # pylint: disable=import-outside-toplevel
                    start_demo_stream,
                )

                start_demo_stream(self.user.id, self.instrument)
                logger.info(
                    "Started demo market data stream for user %s, instrument %s",
                    self.user.username,
                    self.instrument,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to start demo stream: %s", e)

            logger.info(
                "User %s connected to default market data stream for instrument %s",
                self.user.username,
                self.instrument,
            )
            return

        # Validate that the account belongs to the user
        try:
            # Use sync_to_async to query the database
            from channels.db import (  # pylint: disable=import-outside-toplevel
                database_sync_to_async,
            )

            @database_sync_to_async
            def get_account() -> OandaAccount:
                return OandaAccount.objects.get(account_id=self.account_id, user=self.user)

            account = await get_account()

            # Create group name for this account
            self.group_name = f"market_data_{account.id}_{self.instrument}"

            # Join the channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

            # Start the batching task
            if self.is_batching:
                self.batch_task = asyncio.create_task(self._batch_sender())

            logger.info(
                "User %s connected to market data stream for account %s, instrument %s",
                self.user.username,
                self.account_id,
                self.instrument,
            )

        except ObjectDoesNotExist:
            logger.warning(
                "User %s attempted to access account %s they don't own",
                self.user.username,
                self.account_id,
            )
            await self.close(code=4003)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error during WebSocket connection: %s", e)
            await self.close(code=4000)

    async def disconnect(self, code: int) -> None:
        """
        Handle WebSocket disconnection.

        This method:
        1. Cancels the batching task
        2. Flushes any remaining messages
        3. Stops demo stream if applicable
        4. Leaves the channel group
        5. Logs the disconnection

        Args:
            code: WebSocket close code
        """
        # Cancel the batching task
        if self.batch_task and not self.batch_task.done():
            self.batch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.batch_task

        # Flush any remaining messages
        if self.message_buffer:
            await self._flush_batch()

        # Stop demo stream if this is a default account
        if self.account_id == "default" and self.user:
            try:
                from .demo_market_data import (  # pylint: disable=import-outside-toplevel
                    stop_demo_stream,
                )

                stop_demo_stream(self.user.id, self.instrument)
                logger.info(
                    "Stopped demo market data stream for user %s, instrument %s",
                    self.user.username,
                    self.instrument,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to stop demo stream: %s", e)

        # Leave the channel group
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        logger.info(
            "User %s disconnected from market data stream for account %s, instrument %s (code: %s)",
            self.user.username if self.user else "Unknown",
            self.account_id,
            self.instrument,
            code,
        )

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        """
        Handle messages received from the WebSocket client.

        This consumer primarily broadcasts data to clients, but can handle
        client messages for configuration or control purposes.

        Args:
            text_data: Text message from client
            bytes_data: Binary message from client
        """
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "ping":
                    # Respond to ping with pong
                    await self.send(text_data=json.dumps({"type": "pong"}))
                elif message_type == "configure_batching":
                    # Allow client to configure batching
                    self.is_batching = data.get("enabled", True)
                    if "batch_size" in data:
                        self.batch_size = max(1, min(100, data["batch_size"]))
                    if "batch_interval" in data:
                        self.batch_interval = max(0.01, min(1.0, data["batch_interval"]))

                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "batching_configured",
                                "enabled": self.is_batching,
                                "batch_size": self.batch_size,
                                "batch_interval": self.batch_interval,
                            }
                        )
                    )
                else:
                    logger.warning("Unknown message type: %s", message_type)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received from client")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error processing client message: %s", e)

    async def market_data_update(self, event: Dict[str, Any]) -> None:
        """
        Handle market data update events from the channel layer.

        This method is called when a message is sent to the channel group.
        It adds the message to the batch buffer or sends it immediately
        depending on batching configuration.

        Args:
            event: Event data containing tick information
        """
        tick_data = event.get("data")

        if not tick_data:
            logger.warning("Received market data update without data")
            return

        if self.is_batching:
            # Add to batch buffer
            self.message_buffer.append(tick_data)

            # If buffer is full, flush immediately
            if len(self.message_buffer) >= self.batch_size:
                await self._flush_batch()
        else:
            # Send immediately without batching
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "tick",
                        "data": tick_data,
                    }
                )
            )

    async def _batch_sender(self) -> None:
        """
        Background task that periodically flushes the message buffer.

        This task runs continuously while the WebSocket is connected,
        sending batched messages at regular intervals.
        """
        try:
            while True:
                await asyncio.sleep(self.batch_interval)
                if self.message_buffer:
                    await self._flush_batch()
        except asyncio.CancelledError:
            # Task was cancelled, flush remaining messages
            if self.message_buffer:
                await self._flush_batch()
            raise

    async def _flush_batch(self) -> None:
        """
        Send all buffered messages as a single batch.

        This method sends all accumulated tick updates in a single
        WebSocket message to reduce network overhead.
        """
        if not self.message_buffer:
            return

        try:
            # Create batch message
            batch_message = {
                "type": "tick_batch",
                "count": len(self.message_buffer),
                "data": self.message_buffer.copy(),
            }

            # Send the batch
            await self.send(text_data=json.dumps(batch_message))

            # Clear the buffer
            self.message_buffer.clear()

            logger.debug(
                "Sent batch of %d tick updates to account %s",
                batch_message["count"],
                self.account_id,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error flushing message batch: %s", e)
            # Clear buffer even on error to prevent memory buildup
            self.message_buffer.clear()

    async def connection_status(self, event: Dict[str, Any]) -> None:
        """
        Handle connection status update events.

        This method broadcasts connection status changes (connected, disconnected,
        reconnecting) to the client.

        Args:
            event: Event data containing connection status
        """
        status_data = event.get("data")

        if not status_data:
            logger.warning("Received connection status update without data")
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_status",
                    "data": status_data,
                }
            )
        )

    async def error_notification(self, event: Dict[str, Any]) -> None:
        """
        Handle error notification events.

        This method broadcasts error notifications to the client.

        Args:
            event: Event data containing error information
        """
        error_data = event.get("data")

        if not error_data:
            logger.warning("Received error notification without data")
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "data": error_data,
                }
            )
        )

    async def pnl_update(self, event: Dict[str, Any]) -> None:
        """
        Handle P&L update events from the channel layer.

        This method broadcasts position P&L updates to the client,
        ensuring updates occur within 500ms of price changes.

        Args:
            event: Event data containing position P&L information

        Requirements: 9.4
        """
        pnl_data = event.get("data")

        if not pnl_data:
            logger.warning("Received P&L update without data")
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "pnl_update",
                    "data": pnl_data,
                }
            )
        )

    async def demo_reminder(self, event: Dict[str, Any]) -> None:
        """
        Handle demo reminder events from the channel layer.

        This method broadcasts periodic reminders that the user is viewing
        demo data and should register an OANDA account for real data.

        Args:
            event: Event data containing reminder information
        """
        reminder_data = event.get("data")

        if not reminder_data:
            logger.warning("Received demo reminder without data")
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "demo_reminder",
                    "data": reminder_data,
                }
            )
        )


class PositionUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming position updates to frontend clients.

    This consumer:
    - Accepts WebSocket connections from authenticated users
    - Subscribes to position updates for a specific OANDA account
    - Broadcasts position P&L updates to connected clients
    - Updates within 500ms of price changes
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/positions/<account_id>/

    Requirements: 9.4
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer."""
        super().__init__(*args, **kwargs)
        self.account_id: Optional[str] = None
        self.group_name: Optional[str] = None
        self.user = None

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Validates account ownership
        3. Joins the account-specific channel group
        4. Accepts the WebSocket connection
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt for positions")
            await self.close(code=4001)
            return

        # Get account ID from URL route
        self.account_id = self.scope["url_route"]["kwargs"]["account_id"]

        # Validate that the account belongs to the user
        try:
            # Use sync_to_async to query the database
            from channels.db import (  # pylint: disable=import-outside-toplevel
                database_sync_to_async,
            )

            @database_sync_to_async
            def get_account() -> OandaAccount:
                return OandaAccount.objects.get(account_id=self.account_id, user=self.user)

            account = await get_account()

            # Create group name for this account's positions
            self.group_name = f"positions_{account.id}"

            # Join the channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

            logger.info(
                "User %s connected to position updates for account %s",
                self.user.username,
                self.account_id,
            )

        except ObjectDoesNotExist:
            logger.warning(
                "User %s attempted to access account %s they don't own",
                self.user.username,
                self.account_id,
            )
            await self.close(code=4003)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error during WebSocket connection: %s", e)
            await self.close(code=4000)

    async def disconnect(self, code: int) -> None:
        """
        Handle WebSocket disconnection.

        This method:
        1. Leaves the channel group
        2. Logs the disconnection

        Args:
            code: WebSocket close code
        """
        # Leave the channel group
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        logger.info(
            "User %s disconnected from position updates for account %s (code: %s)",
            self.user.username if self.user else "Unknown",
            self.account_id,
            code,
        )

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        """
        Handle messages received from the WebSocket client.

        Args:
            text_data: Text message from client
            bytes_data: Binary message from client
        """
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "ping":
                    # Respond to ping with pong
                    await self.send(text_data=json.dumps({"type": "pong"}))
                else:
                    logger.warning("Unknown message type: %s", message_type)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received from client")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error processing client message: %s", e)

    async def position_update(self, event: Dict[str, Any]) -> None:
        """
        Handle position update events from the channel layer.

        This method is called when a position update is broadcast to the group.
        It forwards the update to the WebSocket client.

        Args:
            event: Event data containing position update information
        """
        # Extract position data from event
        position_data = event.get("data", {})

        # Send position update to WebSocket client
        await self.send(text_data=json.dumps(position_data))

        logger.debug(
            "Position update sent to user %s for position %s",
            self.user.username if self.user else "Unknown",
            position_data.get("position_id"),
        )


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming admin dashboard metrics to admin users.

    This consumer:
    - Accepts WebSocket connections from authenticated admin users only
    - Subscribes to system metrics updates
    - Broadcasts CPU, memory, and system stats to connected admin clients
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/admin/dashboard/
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer."""
        super().__init__(*args, **kwargs)
        self.user = None
        self.group_name = "admin_dashboard"
        self.metrics_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Validates admin privileges
        3. Joins the admin dashboard channel group
        4. Accepts the WebSocket connection
        5. Starts sending periodic metrics
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated and is admin
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt for admin dashboard")
            await self.close(code=4001)
            return

        if not self.user.is_staff:
            logger.warning(
                "Non-admin user %s attempted to connect to admin dashboard",
                self.user.username,
            )
            await self.close(code=4003)
            return

        # Join the admin dashboard channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        # Start sending periodic metrics
        self.metrics_task = asyncio.create_task(self._send_metrics_periodically())

        logger.info(
            "Admin user %s connected to admin dashboard stream",
            self.user.username,
        )

    async def disconnect(self, code: int) -> None:
        """
        Handle WebSocket disconnection.

        This method:
        1. Cancels the metrics task
        2. Leaves the channel group
        3. Logs the disconnection

        Args:
            code: WebSocket close code
        """
        # Cancel the metrics task
        if self.metrics_task and not self.metrics_task.done():
            self.metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.metrics_task

        # Leave the channel group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        logger.info(
            "Admin user %s disconnected from admin dashboard (code: %s)",
            self.user.username if self.user else "Unknown",
            code,
        )

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        """
        Handle messages received from the WebSocket client.

        Args:
            text_data: Text message from client
            bytes_data: Binary message from client
        """
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "ping":
                    # Respond to ping with pong
                    await self.send(text_data=json.dumps({"type": "pong"}))
                else:
                    logger.warning("Unknown message type: %s", message_type)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received from client")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error processing client message: %s", e)

    async def _send_metrics_periodically(self) -> None:
        """
        Background task that periodically sends system metrics.

        This task runs continuously while the WebSocket is connected,
        sending metrics every 5 seconds.
        """
        while True:
            await self._send_system_metrics()
            await asyncio.sleep(5)  # Send metrics every 5 seconds

    async def _send_system_metrics(self) -> None:
        """
        Collect and send system metrics to the client.
        """
        try:
            import psutil  # pylint: disable=import-outside-toplevel

            # Collect system metrics
            metrics = {
                "type": "metrics",
                "data": {
                    "cpu_usage": psutil.cpu_percent(interval=1),
                    "memory_usage": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage("/").percent,
                    "timestamp": asyncio.get_event_loop().time(),
                },
            }

            # Send metrics to client
            await self.send(text_data=json.dumps(metrics))

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error collecting system metrics: %s", e)

    async def dashboard_update(self, event: Dict[str, Any]) -> None:
        """
        Handle dashboard update events from the channel layer.

        This method is called when a dashboard update is broadcast to the group.
        It forwards the update to the WebSocket client.

        Args:
            event: Event data containing dashboard information
        """
        # Extract dashboard data from event
        dashboard_data = event.get("data", {})

        # Send dashboard update to WebSocket client
        await self.send(text_data=json.dumps(dashboard_data))

        logger.debug(
            "Dashboard update sent to user %s",
            self.user.username if self.user else "Unknown",
        )


class AdminNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming admin notifications to admin users.

    This consumer:
    - Accepts WebSocket connections from authenticated admin users only
    - Subscribes to admin notification updates
    - Broadcasts critical events to connected admin clients
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/admin/notifications/

    Requirements: 33.1, 33.2, 33.3, 33.4, 33.5
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer."""
        super().__init__(*args, **kwargs)
        self.user = None
        self.group_name = "admin_notifications"

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Validates admin privileges
        3. Joins the admin notifications channel group
        4. Accepts the WebSocket connection
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated and is admin
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt for admin notifications")
            await self.close(code=4001)
            return

        if not self.user.is_staff:
            logger.warning(
                "Non-admin user %s attempted to connect to admin notifications",
                self.user.username,
            )
            await self.close(code=4003)
            return

        # Join the admin notifications channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        logger.info(
            "Admin user %s connected to admin notifications stream",
            self.user.username,
        )

    async def disconnect(self, code: int) -> None:
        """
        Handle WebSocket disconnection.

        This method:
        1. Leaves the channel group
        2. Logs the disconnection

        Args:
            code: WebSocket close code
        """
        # Leave the channel group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        logger.info(
            "Admin user %s disconnected from admin notifications (code: %s)",
            self.user.username if self.user else "Unknown",
            code,
        )

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        """
        Handle messages received from the WebSocket client.

        Args:
            text_data: Text message from client
            bytes_data: Binary message from client
        """
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "ping":
                    # Respond to ping with pong
                    await self.send(text_data=json.dumps({"type": "pong"}))
                elif message_type == "mark_read":
                    # Mark notification as read
                    notification_id = data.get("notification_id")
                    if notification_id:
                        # Import here to avoid circular imports
                        # pylint: disable=import-outside-toplevel
                        from channels.db import database_sync_to_async

                        from trading.admin_notification_service import AdminNotificationService

                        @database_sync_to_async
                        def mark_read() -> bool:
                            service = AdminNotificationService()
                            return service.mark_as_read(notification_id)

                        success = await mark_read()
                        await self.send(
                            text_data=json.dumps(
                                {
                                    "type": "mark_read_response",
                                    "notification_id": notification_id,
                                    "success": success,
                                }
                            )
                        )
                else:
                    logger.warning("Unknown message type: %s", message_type)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received from client")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error processing client message: %s", e)

    async def admin_notification(self, event: Dict[str, Any]) -> None:
        """
        Handle admin notification events from the channel layer.

        This method is called when a notification is broadcast to the admin group.
        It forwards the notification to the WebSocket client.

        Args:
            event: Event data containing notification information
        """
        # Extract notification data from event
        notification_data = event.get("data", {})

        # Send notification to WebSocket client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "data": notification_data,
                }
            )
        )

        logger.debug(
            "Admin notification sent to user %s: %s",
            self.user.username if self.user else "Unknown",
            notification_data.get("title"),
        )
