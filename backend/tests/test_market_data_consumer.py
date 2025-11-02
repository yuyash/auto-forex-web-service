"""
Tests for MarketDataConsumer WebSocket consumer.

This module tests the real-time market data streaming functionality
via Django Channels WebSocket consumer.
"""

from django.contrib.auth import get_user_model
from django.urls import path

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from accounts.models import OandaAccount
from trading.consumers import MarketDataConsumer

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def oanda_account(db, user):
    """Create a test OANDA account."""
    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token_encrypted",
        api_type="practice",
        balance=10000.00,
    )


@pytest.fixture
def application():
    """Create a test application with routing."""
    return URLRouter(
        [
            path(
                "ws/market-data/<str:account_id>/",
                MarketDataConsumer.as_asgi(),
            ),
        ]
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMarketDataConsumer:
    """Test suite for MarketDataConsumer."""

    async def test_connect_authenticated_user(self, user, oanda_account, application):
        """Test WebSocket connection with authenticated user."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Disconnect
        await communicator.disconnect()

    async def test_connect_unauthenticated_user(self, oanda_account, application):
        """Test WebSocket connection rejection for unauthenticated user."""
        # Create communicator without user
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = None

        # Connect should fail
        connected, close_code = await communicator.connect()
        assert not connected
        assert close_code == 4001

    async def test_connect_wrong_account(self, user, oanda_account, application):
        """Test WebSocket connection rejection for account not owned by user."""
        # Create another user
        other_user = await database_sync_to_async(User.objects.create_user)(
            username="otheruser", email="other@example.com", password="testpass123"
        )

        # Try to connect with wrong user
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = other_user

        # Connect should fail
        connected, close_code = await communicator.connect()
        assert not connected
        assert close_code == 4003

    async def test_receive_tick_update(self, user, oanda_account, application):
        """Test receiving tick updates via WebSocket."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a tick update
        channel_layer = get_channel_layer()
        group_name = f"market_data_{oanda_account.id}"

        tick_data = {
            "instrument": "EUR_USD",
            "time": "2025-01-01T12:00:00.000000Z",
            "bid": 1.1000,
            "ask": 1.1002,
            "mid": 1.1001,
            "spread": 0.0002,
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "market_data_update",
                "data": tick_data,
            },
        )

        # Receive message (with batching, might need to wait)
        response = await communicator.receive_json_from(timeout=2)

        # Check response
        assert response["type"] in ["tick", "tick_batch"]
        if response["type"] == "tick":
            assert response["data"] == tick_data
        else:
            # Batched response
            assert "data" in response
            assert len(response["data"]) > 0

        # Disconnect
        await communicator.disconnect()

    async def test_ping_pong(self, user, oanda_account, application):
        """Test ping-pong message handling."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Send ping
        await communicator.send_json_to({"type": "ping"})

        # Receive pong
        response = await communicator.receive_json_from(timeout=1)
        assert response["type"] == "pong"

        # Disconnect
        await communicator.disconnect()

    async def test_configure_batching(self, user, oanda_account, application):
        """Test configuring message batching."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Configure batching
        await communicator.send_json_to(
            {
                "type": "configure_batching",
                "enabled": False,
                "batch_size": 20,
                "batch_interval": 0.2,
            }
        )

        # Receive configuration confirmation
        response = await communicator.receive_json_from(timeout=1)
        assert response["type"] == "batching_configured"
        assert response["enabled"] is False
        assert response["batch_size"] == 20
        assert response["batch_interval"] == 0.2

        # Disconnect
        await communicator.disconnect()

    async def test_connection_status_update(self, user, oanda_account, application):
        """Test receiving connection status updates."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a connection status update
        channel_layer = get_channel_layer()
        group_name = f"market_data_{oanda_account.id}"

        status_data = {
            "status": "connected",
            "message": "Stream connected successfully",
            "account_id": oanda_account.account_id,
            "is_connected": True,
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "connection_status",
                "data": status_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=1)

        # Check response
        assert response["type"] == "connection_status"
        assert response["data"] == status_data

        # Disconnect
        await communicator.disconnect()

    async def test_error_notification(self, user, oanda_account, application):
        """Test receiving error notifications."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send an error notification
        channel_layer = get_channel_layer()
        group_name = f"market_data_{oanda_account.id}"

        error_data = {
            "error": "Connection failed",
            "message": "Failed to connect to OANDA API",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "error_notification",
                "data": error_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=1)

        # Check response
        assert response["type"] == "error"
        assert response["data"] == error_data

        # Disconnect
        await communicator.disconnect()

    async def test_message_batching(self, user, oanda_account, application):
        """Test message batching functionality."""
        # Create communicator
        communicator = WebsocketCommunicator(
            application, f"/ws/market-data/{oanda_account.account_id}/"
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer
        channel_layer = get_channel_layer()
        group_name = f"market_data_{oanda_account.id}"

        # Send multiple tick updates quickly
        for i in range(5):
            tick_data = {
                "instrument": "EUR_USD",
                "time": f"2025-01-01T12:00:0{i}.000000Z",
                "bid": 1.1000 + i * 0.0001,
                "ask": 1.1002 + i * 0.0001,
                "mid": 1.1001 + i * 0.0001,
                "spread": 0.0002,
            }

            await channel_layer.group_send(
                group_name,
                {
                    "type": "market_data_update",
                    "data": tick_data,
                },
            )

        # Receive batched message
        response = await communicator.receive_json_from(timeout=2)

        # Check response - should be batched
        assert response["type"] == "tick_batch"
        assert "count" in response
        assert "data" in response
        assert len(response["data"]) > 0

        # Disconnect
        await communicator.disconnect()
