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
    - Subscribes to market data updates for a specific OANDA account
    - Broadcasts tick updates to connected clients
    - Implements message batching for performance optimization
    - Handles connection lifecycle (connect, disconnect, receive)

    URL Pattern: ws://host/ws/market-data/<account_id>/

    Requirements: 7.3
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the consumer with batching configuration."""
        super().__init__(*args, **kwargs)
        self.account_id: Optional[str] = None
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

            # Create group name for this account
            self.group_name = f"market_data_{account.id}"

            # Join the channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            # Accept the WebSocket connection
            await self.accept()

            # Start the batching task
            if self.is_batching:
                self.batch_task = asyncio.create_task(self._batch_sender())

            logger.info(
                "User %s connected to market data stream for account %s",
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
            "User %s disconnected from market data stream for account %s (code: %s)",
            self.user.username if self.user else "Unknown",
            self.account_id,
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
