"""Extended integration tests for subscriber task."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone as dj_timezone

from apps.market.models import TickData
from apps.market.tasks.subscriber import TickSubscriberRunner


@pytest.mark.django_db
class TestTickSubscriberRunnerExtendedIntegration:
    """Extended integration tests for TickSubscriberRunner."""

    def test_parse_tick_message_valid(self) -> None:
        """Test parsing valid tick message."""
        runner = TickSubscriberRunner()

        data_raw = '{"instrument": "EUR_USD", "timestamp": "2024-01-01T00:00:00Z", "bid": "1.10000", "ask": "1.10010", "mid": "1.10005"}'

        tick = runner._parse_tick_message(data_raw)

        assert tick is not None
        assert tick.instrument == "EUR_USD"
        assert tick.bid == Decimal("1.10000")
        assert tick.ask == Decimal("1.10010")
        assert tick.mid == Decimal("1.10005")

    def test_parse_tick_message_invalid_json(self) -> None:
        """Test parsing invalid JSON."""
        runner = TickSubscriberRunner()

        data_raw = "invalid json"

        tick = runner._parse_tick_message(data_raw)

        assert tick is None

    def test_parse_tick_message_missing_fields(self) -> None:
        """Test parsing message with missing fields."""
        runner = TickSubscriberRunner()

        data_raw = '{"instrument": "EUR_USD"}'

        tick = runner._parse_tick_message(data_raw)

        assert tick is None

    def test_flush_buffer_empty(self) -> None:
        """Test flushing empty buffer."""
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()

        # Should not raise exception
        runner._flush_buffer()

        assert len(runner.buffer) == 0

    def test_flush_buffer_with_data(self) -> None:
        """Test flushing buffer with tick data."""
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()

        # Add tick to buffer with timezone-aware datetime
        now = dj_timezone.now()
        tick = TickData(
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
            mid=Decimal("1.10005"),
        )
        runner.buffer.append(tick)

        # Flush buffer
        runner._flush_buffer()

        # Buffer should be cleared
        assert len(runner.buffer) == 0

        # Tick should be in database
        saved_tick = TickData.objects.filter(
            instrument="EUR_USD",
            timestamp=now,
        ).first()

        assert saved_tick is not None

    @patch("apps.market.tasks.subscriber.redis_client")
    @patch("apps.market.tasks.subscriber.CeleryTaskService")
    def test_cleanup_and_stop(self, mock_service: Any, mock_redis: Any) -> None:
        """Test cleanup and stop method."""
        mock_service_instance = MagicMock()
        mock_service.return_value = mock_service_instance

        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        runner = TickSubscriberRunner()
        runner.task_service = mock_service_instance

        # Should not raise exception
        runner._cleanup_and_stop(
            client=mock_client,
            lock_key="test_lock",
            pubsub=None,
            message="Test stop",
        )

        # Verify cleanup was called
        assert mock_service_instance.mark_stopped.called
