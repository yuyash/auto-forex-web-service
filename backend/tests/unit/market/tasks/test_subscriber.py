"""Unit tests for TickSubscriberRunner."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.market.tasks.subscriber import TickSubscriberRunner


class TestTickSubscriberRunnerInit:
    """Tests for __init__."""

    def test_initial_attributes(self):
        runner = TickSubscriberRunner()

        assert runner.task_service is None
        assert runner.buffer == []
        assert runner.buffer_max == 200
        assert runner.flush_interval_seconds == 2


class TestTickSubscriberRunnerRun:
    """Tests for run method."""

    @patch("apps.market.tasks.subscriber.redis_client")
    @patch("apps.market.tasks.subscriber.acquire_lock", return_value=False)
    @patch("apps.market.tasks.subscriber.current_task_id", return_value="task-1")
    @patch("apps.market.tasks.subscriber.lock_value", return_value="worker-1")
    @patch("apps.market.tasks.subscriber.CeleryTaskService")
    @patch("apps.market.tasks.subscriber.settings")
    def test_run_already_locked_stops(
        self, mock_settings, MockService, mock_lock_val, mock_task_id, mock_acquire, mock_redis
    ):
        mock_settings.MARKET_REDIS_URL = "redis://localhost"
        mock_settings.MARKET_TICK_CHANNEL = "ticks"
        mock_settings.MARKET_TICK_SUBSCRIBER_LOCK_KEY = "lock:sub"

        svc_instance = MagicMock()
        svc_instance.should_stop.return_value = False
        MockService.return_value = svc_instance

        client = MagicMock()
        mock_redis.return_value = client

        runner = TickSubscriberRunner()
        runner.run()

        svc_instance.mark_stopped.assert_called_once()

    @patch("apps.market.tasks.subscriber.redis_client")
    @patch("apps.market.tasks.subscriber.acquire_lock", return_value=True)
    @patch("apps.market.tasks.subscriber.current_task_id", return_value="task-1")
    @patch("apps.market.tasks.subscriber.lock_value", return_value="worker-1")
    @patch("apps.market.tasks.subscriber.CeleryTaskService")
    @patch("apps.market.tasks.subscriber.settings")
    def test_run_stop_requested_immediately(
        self, mock_settings, MockService, mock_lock_val, mock_task_id, mock_acquire, mock_redis
    ):
        mock_settings.MARKET_REDIS_URL = "redis://localhost"
        mock_settings.MARKET_TICK_CHANNEL = "ticks"
        mock_settings.MARKET_TICK_SUBSCRIBER_LOCK_KEY = "lock:sub"

        svc_instance = MagicMock()
        svc_instance.should_stop.return_value = True
        MockService.return_value = svc_instance

        client = MagicMock()
        mock_redis.return_value = client

        runner = TickSubscriberRunner()
        runner.run()

        svc_instance.mark_stopped.assert_called_once()


class TestParseTickMessage:
    """Tests for _parse_tick_message."""

    def test_valid_tick_returns_tick_data(self):
        runner = TickSubscriberRunner()

        payload = json.dumps(
            {
                "instrument": "EUR_USD",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "bid": "1.10000",
                "ask": "1.10010",
                "mid": "1.10005",
            }
        )

        result = runner._parse_tick_message(payload)

        assert result is not None
        assert result.instrument == "EUR_USD"
        assert result.bid == Decimal("1.10000")
        assert result.ask == Decimal("1.10010")
        assert result.mid == Decimal("1.10005")

    def test_invalid_json_returns_none(self):
        runner = TickSubscriberRunner()
        result = runner._parse_tick_message("not-json")
        assert result is None

    def test_missing_instrument_returns_none(self):
        runner = TickSubscriberRunner()
        payload = json.dumps(
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "bid": "1.10000",
                "ask": "1.10010",
                "mid": "1.10005",
            }
        )
        result = runner._parse_tick_message(payload)
        assert result is None

    def test_empty_instrument_returns_none(self):
        runner = TickSubscriberRunner()
        payload = json.dumps(
            {
                "instrument": "",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "bid": "1.10000",
                "ask": "1.10010",
                "mid": "1.10005",
            }
        )
        result = runner._parse_tick_message(payload)
        assert result is None

    def test_malformed_fields_returns_none(self):
        runner = TickSubscriberRunner()
        payload = json.dumps(
            {
                "instrument": "EUR_USD",
                "timestamp": "not-a-date",
                "bid": "not-a-number",
                "ask": "1.10010",
                "mid": "1.10005",
            }
        )
        result = runner._parse_tick_message(payload)
        assert result is None


class TestFlushBuffer:
    """Tests for _flush_buffer."""

    @patch("apps.market.tasks.subscriber.TickData")
    def test_flush_empty_buffer_does_nothing(self, MockTickData):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()
        runner.buffer = []

        runner._flush_buffer()

        MockTickData.objects.bulk_create.assert_not_called()

    @patch("apps.market.tasks.subscriber.TickData")
    def test_flush_buffer_calls_bulk_create(self, MockTickData):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()

        tick = MagicMock()
        tick.instrument = "EUR_USD"
        tick.timestamp = MagicMock()
        runner.buffer = [tick]

        runner._flush_buffer()

        MockTickData.objects.bulk_create.assert_called_once()
        assert runner.buffer == []

    @patch("apps.market.tasks.subscriber.TickData")
    def test_flush_deduplicates_by_instrument_timestamp(self, MockTickData):
        from datetime import datetime, timezone

        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()

        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tick1 = MagicMock()
        tick1.instrument = "EUR_USD"
        tick1.timestamp = ts
        tick2 = MagicMock()
        tick2.instrument = "EUR_USD"
        tick2.timestamp = ts

        runner.buffer = [tick1, tick2]
        runner._flush_buffer()

        call_args = MockTickData.objects.bulk_create.call_args
        # Should deduplicate to 1 tick
        assert len(call_args[0][0]) == 1

    @patch("apps.market.tasks.subscriber.TickData")
    def test_flush_handles_db_error_gracefully(self, MockTickData):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()

        tick = MagicMock()
        tick.instrument = "EUR_USD"
        tick.timestamp = MagicMock()
        runner.buffer = [tick]

        MockTickData.objects.bulk_create.side_effect = Exception("db error")

        # Should not raise
        runner._flush_buffer()


class TestCleanupAndStop:
    """Tests for _cleanup_and_stop."""

    def test_flushes_buffer_and_cleans_up(self):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()
        runner.buffer = []

        client = MagicMock()
        pubsub = MagicMock()

        runner._cleanup_and_stop(client, "lock:key", pubsub, "done")

        pubsub.close.assert_called_once()
        client.delete.assert_called_once_with("lock:key")
        client.close.assert_called_once()
        runner.task_service.mark_stopped.assert_called_once()

    def test_handles_none_pubsub(self):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()
        runner.buffer = []

        client = MagicMock()

        # Should not raise
        runner._cleanup_and_stop(client, "lock:key", None, "done")
        runner.task_service.mark_stopped.assert_called_once()

    def test_handles_client_errors_gracefully(self):
        runner = TickSubscriberRunner()
        runner.task_service = MagicMock()
        runner.buffer = []

        client = MagicMock()
        client.delete.side_effect = Exception("redis down")
        client.close.side_effect = Exception("redis down")

        pubsub = MagicMock()
        pubsub.close.side_effect = Exception("redis down")

        # Should not raise
        runner._cleanup_and_stop(client, "lock:key", pubsub, "done")
        runner.task_service.mark_stopped.assert_called_once()
