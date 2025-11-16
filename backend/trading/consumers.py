"""
WebSocket consumers for real-time market data streaming.

This module implements Django Channels consumers for broadcasting
real-time market data updates to connected frontend clients.
"""

# pylint: disable=too-many-lines

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
    - Subscribes to market data updates for a specific OANDA account.
    - Broadcasts tick updates to connected clients
    - Implements message batching for performance optimization
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/market-data/<account_id>/<instrument>/
    - account_id: OANDA account ID
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
        2. Validates account ownership
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

        # Reject "default" account - require actual OANDA account
        if self.account_id == "default":
            logger.warning(
                "User %s attempted to connect without OANDA account",
                self.user.username,
            )
            await self.close(code=4003, reason="OANDA account required")
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
        3. Leaves the channel group
        4. Logs the disconnection

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
        self.external_api_task: Optional[asyncio.Task] = None

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

        # Start sending periodic metrics (fast cycle - internal system health)
        self.metrics_task = asyncio.create_task(self._send_metrics_periodically())

        # Start checking external APIs (slow cycle - external services)
        self.external_api_task = asyncio.create_task(self._check_external_apis_periodically())

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

        # Cancel the external API check task
        if self.external_api_task and not self.external_api_task.done():
            self.external_api_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.external_api_task

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
        Background task that periodically sends system metrics and dashboard data.

        This task runs continuously while the WebSocket is connected,
        sending full dashboard updates based on system settings interval.
        """
        from channels.db import database_sync_to_async

        from accounts.models import SystemSettings

        @database_sync_to_async
        def get_update_interval() -> int:
            try:
                settings = SystemSettings.get_settings()
                interval = getattr(settings, "system_health_update_interval", 5)
                logger.info(
                    "Retrieved system_health_update_interval: %s (type: %s)",
                    interval,
                    type(interval).__name__,
                )
                return interval
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error getting update interval: %s", e)
                return 5  # Default to 5 seconds on error

        while True:
            start_time = asyncio.get_event_loop().time()
            await self._send_dashboard_data()
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            interval = await get_update_interval()
            logger.info(
                "Dashboard data sent to admin user %s (took %.2fs), next update in %s seconds",
                self.user.username if self.user else "Unknown",
                execution_time,
                interval,
            )
            await asyncio.sleep(interval)

    async def _send_dashboard_data(self) -> None:
        """
        Collect and send complete dashboard data to the client.
        """
        try:
            import psutil  # pylint: disable=import-outside-toplevel
            from channels.db import (  # pylint: disable=import-outside-toplevel
                database_sync_to_async,
            )

            from accounts.models import UserSession  # pylint: disable=import-outside-toplevel
            from trading.models import Strategy  # pylint: disable=import-outside-toplevel
            from trading.system_health_monitor import (  # pylint: disable=import-outside-toplevel
                SystemHealthMonitor,
            )

            @database_sync_to_async
            def get_dashboard_data() -> Dict[str, Any]:
                # Get system health (exclude external API checks for performance)
                monitor = SystemHealthMonitor()
                health_data = monitor.get_health_summary(include_external_apis=False)

                # Transform health data
                # Note: oanda_api_status is NOT included here - it's sent separately
                # via external_api_update messages to avoid performance issues
                health = {
                    "cpu_usage": health_data.get("cpu", {}).get("cpu_percent", 0),
                    "memory_usage": health_data.get("memory", {}).get("percent", 0),
                    "disk_usage": psutil.disk_usage("/").percent,
                    "database_status": (
                        "connected"
                        if health_data.get("database", {}).get("connected")
                        else "disconnected"
                    ),
                    "redis_status": (
                        "connected"
                        if health_data.get("redis", {}).get("connected")
                        else "disconnected"
                    ),
                    "active_streams": health_data.get("active_streams", 0),
                    "celery_tasks": health_data.get("celery_tasks", {}).get("total", 0),
                    "timestamp": health_data.get("timestamp"),
                }

                # Get online users with session details
                active_sessions = (
                    UserSession.objects.filter(is_active=True)
                    .select_related("user")
                    .order_by("-last_activity")
                )

                online_users = [
                    {
                        "user_id": session.user.id,
                        "username": session.user.username,
                        "email": session.user.email,
                        "session_id": session.id,
                        "session_key": session.session_key,
                        "ip_address": session.ip_address,
                        "user_agent": session.user_agent,
                        "login_time": session.login_time.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "is_staff": session.user.is_staff,
                    }
                    for session in active_sessions
                ]

                # Get running strategies
                active_strategies = (
                    Strategy.objects.filter(is_active=True)
                    .select_related("account__user")
                    .prefetch_related("account__positions")
                )

                running_strategies = []
                for strategy in active_strategies:
                    positions = strategy.account.positions.filter(
                        opened_at__isnull=False, closed_at__isnull=True
                    )
                    position_count = positions.count()
                    total_pnl = sum(pos.unrealized_pnl for pos in positions)

                    running_strategies.append(
                        {
                            "strategy_id": strategy.id,
                            "strategy_type": strategy.strategy_type,
                            "user_id": strategy.account.user.id,
                            "username": strategy.account.user.username,
                            "email": strategy.account.user.email,
                            "account_id": strategy.account.id,
                            "oanda_account_id": strategy.account.account_id,
                            "instrument": strategy.instrument,
                            "started_at": (
                                strategy.started_at.isoformat() if strategy.started_at else None
                            ),
                            "position_count": position_count,
                            "total_unrealized_pnl": float(total_pnl),
                        }
                    )

                return {
                    "health": health,
                    "online_users": online_users,
                    "running_strategies": running_strategies,
                }

            # Get dashboard data
            dashboard_data = await get_dashboard_data()

            # Send complete dashboard update
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "dashboard_update",
                        "data": dashboard_data,
                    }
                )
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error collecting dashboard data: %s", e)

    async def _check_external_apis_periodically(self) -> None:
        """
        Background task that periodically checks external API health.

        This task runs on a longer interval (default 60s) to avoid
        frequent timeouts and performance issues with external services.
        Sends an immediate check on connection, then continues with regular interval.
        """
        from channels.db import database_sync_to_async

        from accounts.models import SystemSettings
        from trading.system_health_monitor import SystemHealthMonitor

        @database_sync_to_async
        def get_external_api_interval() -> int:
            try:
                settings = SystemSettings.get_settings()
                return getattr(settings, "external_api_check_interval", 60)
            except Exception:  # pylint: disable=broad-exception-caught
                return 60  # Default to 60 seconds on error

        @database_sync_to_async
        def get_oanda_api_status() -> Dict[str, Any]:
            from django.utils import timezone as tz

            monitor = SystemHealthMonitor()
            status = monitor.check_oanda_api_connection()
            status["timestamp"] = tz.now().isoformat()
            return status

        # Send immediate check on connection (don't wait for first interval)
        try:
            oanda_status = await get_oanda_api_status()
            message_data = {
                "type": "external_api_update",
                "data": {
                    "oanda_api": oanda_status,
                },
            }
            await self.send(text_data=json.dumps(message_data))
            logger.info(
                "Initial external API status sent to admin user %s (status: %s)",
                self.user.username if self.user else "Unknown",
                oanda_status.get("status"),
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error sending initial external API status: %s", e)

        # Continue with regular interval checks
        while True:
            try:
                interval = await get_external_api_interval()
                await asyncio.sleep(interval)

                # Check OANDA API status
                oanda_status = await get_oanda_api_status()

                # Send external API status update
                message_data = {
                    "type": "external_api_update",
                    "data": {
                        "oanda_api": oanda_status,
                    },
                }
                await self.send(text_data=json.dumps(message_data))

                logger.info(
                    (
                        "External API status sent to admin user %s (status: %s), "
                        "next check in %s seconds"
                    ),
                    self.user.username if self.user else "Unknown",
                    oanda_status.get("status"),
                    interval,
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error checking external APIs: %s", e)
                await asyncio.sleep(60)  # Wait before retrying on error

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


class TaskLogsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming task execution logs in real-time.

    This consumer:
    - Accepts WebSocket connections from authenticated users
    - Subscribes to log updates for a specific task
    - Broadcasts log entries as they are created
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/tasks/<task_type>/<task_id>/logs/
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer."""
        super().__init__(*args, **kwargs)
        self.user = None
        self.task_type: Optional[str] = None
        self.task_id: Optional[int] = None
        self.group_name: Optional[str] = None

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Validates task ownership
        3. Joins the task-specific log channel group
        4. Accepts the WebSocket connection
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt for task logs")
            await self.close(code=4001)
            return

        # Get task type and ID from URL route
        self.task_type = self.scope["url_route"]["kwargs"]["task_type"]
        self.task_id = int(self.scope["url_route"]["kwargs"]["task_id"])

        # Validate that the task belongs to the user
        try:
            from channels.db import database_sync_to_async

            @database_sync_to_async
            def validate_task_ownership() -> bool:
                if self.task_type == "backtest":
                    from trading.backtest_task_models import BacktestTask

                    return BacktestTask.objects.filter(id=self.task_id, user=self.user).exists()
                if self.task_type == "trading":
                    from trading.trading_task_models import TradingTask

                    return TradingTask.objects.filter(id=self.task_id, user=self.user).exists()
                return False

            is_owner = await validate_task_ownership()

            if not is_owner:
                logger.warning(
                    "User %s attempted to access logs for task %s/%s they don't own",
                    self.user.username,
                    self.task_type,
                    self.task_id,
                )
                await self.close(code=4003)
                return

            # Create group name for this task's logs
            self.group_name = f"task_logs_{self.task_type}_{self.task_id}"

            # Join the channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

            logger.info(
                "User %s connected to logs for %s task %s",
                self.user.username,
                self.task_type,
                self.task_id,
            )

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
            "User %s disconnected from logs for %s task %s (code: %s)",
            self.user.username if self.user else "Unknown",
            self.task_type,
            self.task_id,
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

    async def execution_log(self, event: Dict[str, Any]) -> None:
        """
        Handle execution log events from the channel layer.

        This method is called when a new log entry is added to the execution.
        It forwards the log to the WebSocket client.

        Args:
            event: Event data containing log information
        """
        # Extract log data from event
        log_data = event.get("data", {})

        # Send log update to WebSocket client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "execution_log",
                    "data": log_data,
                }
            )
        )

        logger.debug(
            "Log sent to user %s for execution %s: %s",
            self.user.username if self.user else "Unknown",
            log_data.get("execution_id"),
            log_data.get("log", {}).get("message", "")[:50],
        )


class TaskStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming task status updates and logs to users.

    This consumer:
    - Accepts WebSocket connections from authenticated users
    - Subscribes to task status updates for the user's tasks
    - Subscribes to execution log updates for the user's tasks
    - Broadcasts status changes (completed, failed, stopped) to connected clients
    - Broadcasts real-time execution logs to connected clients
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/tasks/status/

    Requirements: 3.3, 3.4, 3.5, 6.7
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer."""
        super().__init__(*args, **kwargs)
        self.user = None
        self.status_group_name: Optional[str] = None

    async def connect(self) -> None:
        """
        Handle WebSocket connection.

        This method:
        1. Authenticates the user
        2. Joins the user-specific task status channel group
        3. Accepts the WebSocket connection

        Requirements: 3.3, 3.4
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get("user")

        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt for task status")
            await self.close(code=4001)
            return

        # Create group name for this user's tasks
        self.status_group_name = f"task_status_user_{self.user.id}"

        # Join the channel group for status updates
        await self.channel_layer.group_add(self.status_group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        logger.info(
            "User %s connected to task status updates and logs",
            self.user.username,
        )

    async def disconnect(self, code: int) -> None:
        """
        Handle WebSocket disconnection.

        This method:
        1. Leaves the channel groups
        2. Logs the disconnection

        Args:
            code: WebSocket close code

        Requirements: 3.3
        """
        # Leave the status channel group
        if self.status_group_name:
            await self.channel_layer.group_discard(self.status_group_name, self.channel_name)

        logger.info(
            "User %s disconnected from task status updates (code: %s)",
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

    async def task_status_update(self, event: Dict[str, Any]) -> None:
        """
        Handle task status update events from the channel layer.

        This method is called when a task status changes (completed, failed, stopped).
        It forwards the update to the WebSocket client.

        Args:
            event: Event data containing task status information
        """
        # Extract task data from event
        task_data = event.get("data", {})

        # Send task status update to WebSocket client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "task_status_update",
                    "data": task_data,
                }
            )
        )

        logger.debug(
            "Task status update sent to user %s: task %s is now %s",
            self.user.username if self.user else "Unknown",
            task_data.get("task_id"),
            task_data.get("status"),
        )

    async def task_progress_update(self, event: Dict[str, Any]) -> None:
        """
        Handle task progress update events from the channel layer.

        This method is called when a task execution progress changes.
        It forwards the progress update to the WebSocket client.

        Args:
            event: Event data containing task progress information
        """
        # Extract progress data from event
        progress_data = event.get("data", {})

        # Send task progress update to WebSocket client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "task_progress_update",
                    "data": progress_data,
                }
            )
        )

        logger.debug(
            "Task progress update sent to user %s: task %s is at %s%%",
            self.user.username if self.user else "Unknown",
            progress_data.get("task_id"),
            progress_data.get("progress"),
        )

    async def backtest_intermediate_results(self, event: Dict[str, Any]) -> None:
        """
        Handle intermediate backtest results from the channel layer.

        This method is called after each day is processed during incremental backtest.
        It forwards the intermediate results to the WebSocket client.

        Args:
            event: Event data containing intermediate backtest results
        """
        # Extract results data from event
        results_data = event.get("data", {})

        # Send intermediate results to WebSocket client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "backtest_intermediate_results",
                    "data": results_data,
                }
            )
        )

        logger.debug(
            "Backtest intermediate results sent to user %s: task %s day %s/%s",
            self.user.username if self.user else "Unknown",
            results_data.get("task_id"),
            results_data.get("days_processed"),
            results_data.get("total_days"),
        )

    async def execution_log(self, event: Dict[str, Any]) -> None:
        """
        Handle execution log events from the channel layer.

        This method is called when a new log entry is generated during task execution.
        It verifies task ownership before forwarding the log to the WebSocket client.

        Args:
            event: Event data containing log information

        Requirements: 6.7
        """
        log_data = event.get("data")

        if not log_data:
            logger.warning("Received execution log event without data")
            return

        # Verify user owns this task
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def check_ownership() -> bool:
            """Check if the user owns the task."""
            task_id = log_data.get("task_id")
            task_type = log_data.get("task_type")

            if not task_id or not task_type:
                return False

            if task_type == "backtest":
                from trading.backtest_task_models import BacktestTask

                return BacktestTask.objects.filter(id=task_id, user=self.user).exists()
            if task_type == "trading":
                from trading.trading_task_models import TradingTask

                return TradingTask.objects.filter(id=task_id, user=self.user).exists()
            return False

        # Only send log if user owns the task
        if await check_ownership():
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "execution_log",
                        "data": log_data,
                    }
                )
            )

            logger.debug(
                "Execution log sent to user %s for task %s/%s: %s",
                self.user.username if self.user else "Unknown",
                log_data.get("task_type"),
                log_data.get("task_id"),
                log_data.get("log", {}).get("message", "")[:50],
            )
        else:
            logger.warning(
                "User %s attempted to receive logs for task %s/%s they don't own",
                self.user.username if self.user else "Unknown",
                log_data.get("task_type"),
                log_data.get("task_id"),
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
