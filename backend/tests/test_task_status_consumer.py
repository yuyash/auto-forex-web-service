"""
Tests for TaskStatusConsumer WebSocket consumer.

This module tests the real-time task status updates and log streaming
functionality via Django Channels WebSocket consumer.

Requirements: 3.3, 3.4, 6.7
"""

from django.contrib.auth import get_user_model
from django.urls import path

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from trading.backtest_task_models import BacktestTask
from trading.consumers import TaskStatusConsumer
from trading.enums import TaskStatus

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        username="otheruser", email="other@example.com", password="testpass456"
    )


@pytest.fixture
def strategy_config(db, user):
    """Create a test strategy config."""
    from trading.models import StrategyConfig

    return StrategyConfig.objects.create(
        user=user,
        name="Test Config",
        strategy_type="ma_crossover",
        parameters={},
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create a test backtest task."""
    return BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        instrument="EUR_USD",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-03T23:59:59Z",
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def application():
    """Create a test application with routing."""
    return URLRouter(
        [
            path("ws/tasks/status/", TaskStatusConsumer.as_asgi()),
        ]
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestTaskStatusConsumer:
    """Test suite for TaskStatusConsumer."""

    async def test_connect_authenticated_user(self, user, application):
        """
        Test WebSocket connection with authenticated user.

        Requirements: 3.3, 3.4
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Disconnect
        await communicator.disconnect()

    async def test_connect_unauthenticated_user(self, application):
        """
        Test WebSocket connection rejection for unauthenticated user.

        Requirements: 3.3
        """
        # Create communicator without user
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = None

        # Connect should fail
        connected, close_code = await communicator.connect()
        assert not connected
        assert close_code == 4001

    async def test_task_status_update(self, user, backtest_task, application):
        """
        Test receiving task status updates via WebSocket.

        Requirements: 3.4
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a status update
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        status_data = {
            "task_id": backtest_task.id,
            "task_name": backtest_task.name,
            "task_type": "backtest",
            "status": TaskStatus.RUNNING,
            "execution_id": 123,
            "timestamp": "2025-11-15T20:50:36Z",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "task_status_update",
                "data": status_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=2)

        # Check response
        assert response["type"] == "task_status_update"
        assert response["data"]["task_id"] == backtest_task.id
        assert response["data"]["status"] == TaskStatus.RUNNING
        assert response["data"]["execution_id"] == 123

        # Disconnect
        await communicator.disconnect()

    async def test_task_progress_update(self, user, backtest_task, application):
        """
        Test receiving task progress updates via WebSocket.

        Requirements: 3.4
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a progress update
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        progress_data = {
            "task_id": backtest_task.id,
            "task_type": "backtest",
            "execution_id": 123,
            "progress": 50,
            "timestamp": "2025-11-15T20:50:36Z",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "task_progress_update",
                "data": progress_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=2)

        # Check response
        assert response["type"] == "task_progress_update"
        assert response["data"]["task_id"] == backtest_task.id
        assert response["data"]["progress"] == 50
        assert response["data"]["execution_id"] == 123

        # Disconnect
        await communicator.disconnect()

    async def test_backtest_intermediate_results(self, user, backtest_task, application):
        """
        Test receiving intermediate backtest results via WebSocket.

        Requirements: 3.4
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send intermediate results
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        results_data = {
            "task_id": backtest_task.id,
            "task_type": "backtest",
            "execution_id": 123,
            "days_processed": 1,
            "total_days": 3,
            "timestamp": "2025-11-15T20:50:36Z",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "backtest_intermediate_results",
                "data": results_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=2)

        # Check response
        assert response["type"] == "backtest_intermediate_results"
        assert response["data"]["task_id"] == backtest_task.id
        assert response["data"]["days_processed"] == 1
        assert response["data"]["total_days"] == 3

        # Disconnect
        await communicator.disconnect()

    async def test_execution_log_with_ownership(self, user, backtest_task, application):
        """
        Test receiving execution logs for owned tasks.

        Requirements: 6.7
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a log entry
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        log_data = {
            "task_id": backtest_task.id,
            "task_type": "backtest",
            "execution_id": 123,
            "execution_number": 1,
            "log": {
                "timestamp": "2025-11-15T20:50:36Z",
                "level": "INFO",
                "message": "Starting backtest: 3 days (2025-01-01 to 2025-01-03)",
            },
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "execution_log",
                "data": log_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=2)

        # Check response
        assert response["type"] == "execution_log"
        assert response["data"]["task_id"] == backtest_task.id
        assert response["data"]["log"]["level"] == "INFO"
        assert "Starting backtest" in response["data"]["log"]["message"]

        # Disconnect
        await communicator.disconnect()

    async def test_execution_log_without_ownership(
        self, user, other_user, strategy_config, application
    ):
        """
        Test that users don't receive logs for tasks they don't own.

        Requirements: 6.7
        """
        # Create a config for other_user
        from trading.models import StrategyConfig

        @database_sync_to_async
        def create_other_config():
            return StrategyConfig.objects.create(
                user=other_user,
                name="Other Config",
                strategy_type="ma_crossover",
                parameters={},
            )

        other_config = await create_other_config()

        # Create a task owned by other_user
        other_task = await database_sync_to_async(BacktestTask.objects.create)(
            user=other_user,
            config=other_config,
            name="Other User's Backtest",
            instrument="EUR_USD",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-03T23:59:59Z",
            status=TaskStatus.CREATED,
        )

        # Create communicator for user (not the owner)
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer and send a log entry for other_user's task
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        log_data = {
            "task_id": other_task.id,
            "task_type": "backtest",
            "execution_id": 123,
            "execution_number": 1,
            "log": {
                "timestamp": "2025-11-15T20:50:36Z",
                "level": "INFO",
                "message": "This should not be received",
            },
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "execution_log",
                "data": log_data,
            },
        )

        # Should not receive any message (timeout expected)
        import asyncio
        import contextlib

        with pytest.raises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=1)

        # Disconnect (may raise CancelledError during cleanup, which is expected)
        with contextlib.suppress(asyncio.CancelledError):
            await communicator.disconnect()

    async def test_ping_pong(self, user, application):
        """
        Test ping-pong message handling.

        Requirements: 3.3
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
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

    async def test_group_subscription(self, user, application):
        """
        Test that consumer subscribes to correct channel group.

        Requirements: 3.3
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Verify group subscription by sending a message
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        test_data = {
            "task_id": 999,
            "task_name": "Test Task",
            "task_type": "backtest",
            "status": TaskStatus.COMPLETED,
            "execution_id": 456,
            "timestamp": "2025-11-15T20:50:36Z",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "task_status_update",
                "data": test_data,
            },
        )

        # Should receive the message
        response = await communicator.receive_json_from(timeout=2)
        assert response["type"] == "task_status_update"
        assert response["data"]["task_id"] == 999

        # Disconnect
        await communicator.disconnect()

    async def test_group_unsubscription_on_disconnect(self, user, application):
        """
        Test that consumer unsubscribes from channel group on disconnect.

        Requirements: 3.3
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Disconnect
        await communicator.disconnect()

        # Try to send a message to the group
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        test_data = {
            "task_id": 999,
            "task_name": "Test Task",
            "task_type": "backtest",
            "status": TaskStatus.COMPLETED,
            "execution_id": 456,
            "timestamp": "2025-11-15T20:50:36Z",
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "task_status_update",
                "data": test_data,
            },
        )

        # Create a new communicator to verify no messages are queued
        new_communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        new_communicator.scope["user"] = user

        connected, _ = await new_communicator.connect()
        assert connected

        # Should not receive the old message (timeout expected)
        import asyncio
        import contextlib

        with pytest.raises(asyncio.TimeoutError):
            await new_communicator.receive_json_from(timeout=1)

        # Disconnect (may raise CancelledError during cleanup, which is expected)
        with contextlib.suppress(asyncio.CancelledError):
            await new_communicator.disconnect()

    async def test_multiple_log_entries(self, user, backtest_task, application):
        """
        Test receiving multiple log entries in sequence.

        Requirements: 6.7
        """
        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        # Send multiple log entries
        log_messages = [
            "Starting backtest: 3 days",
            "Day 1/3: 2025-01-01 - Fetching data...",
            "Day 1/3: Processing 520656 ticks...",
            "Day 1/3: Complete (50.00s)",
        ]

        for i, message in enumerate(log_messages):
            log_data = {
                "task_id": backtest_task.id,
                "task_type": "backtest",
                "execution_id": 123,
                "execution_number": 1,
                "log": {
                    "timestamp": f"2025-11-15T20:50:{i:02d}Z",
                    "level": "INFO",
                    "message": message,
                },
            }

            await channel_layer.group_send(
                group_name,
                {
                    "type": "execution_log",
                    "data": log_data,
                },
            )

        # Receive all messages
        received_messages = []
        for _ in range(len(log_messages)):
            response = await communicator.receive_json_from(timeout=2)
            assert response["type"] == "execution_log"
            received_messages.append(response["data"]["log"]["message"])

        # Verify all messages were received in order
        assert received_messages == log_messages

        # Disconnect
        await communicator.disconnect()

    async def test_log_filtering_by_task_type(self, user, strategy_config, application):
        """
        Test that log filtering works correctly for different task types.

        Requirements: 6.7
        """
        # Create a backtest task
        backtest_task = await database_sync_to_async(BacktestTask.objects.create)(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            instrument="EUR_USD",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-03T23:59:59Z",
            status=TaskStatus.CREATED,
        )

        # Create communicator
        communicator = WebsocketCommunicator(application, "/ws/tasks/status/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer
        channel_layer = get_channel_layer()
        group_name = f"task_status_user_{user.id}"

        # Send log for backtest task
        log_data = {
            "task_id": backtest_task.id,
            "task_type": "backtest",
            "execution_id": 123,
            "execution_number": 1,
            "log": {
                "timestamp": "2025-11-15T20:50:36Z",
                "level": "INFO",
                "message": "Backtest log message",
            },
        }

        await channel_layer.group_send(
            group_name,
            {
                "type": "execution_log",
                "data": log_data,
            },
        )

        # Receive message
        response = await communicator.receive_json_from(timeout=2)
        assert response["type"] == "execution_log"
        assert response["data"]["task_type"] == "backtest"
        assert "Backtest log message" in response["data"]["log"]["message"]

        # Disconnect
        await communicator.disconnect()
