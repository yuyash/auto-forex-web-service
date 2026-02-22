"""Integration tests for RedisTickDataSource.__iter__ with fakeredis.

Tests the full streaming loop by publishing messages to a fake Redis
pub/sub channel and verifying the iterator yields correct Tick batches.
"""

import json
import threading
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from apps.trading.tasks.source import RedisTickDataSource


def _publish_ticks(fake_server, channel, ticks, delay=0.05, eof=True):
    """Publish tick messages to a fakeredis channel in a background thread."""
    client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
    time.sleep(delay)
    for tick in ticks:
        client.publish(channel, json.dumps(tick))
        time.sleep(0.01)
    if eof:
        time.sleep(0.01)
        client.publish(channel, json.dumps({"type": "eof"}))
    client.close()


@pytest.mark.django_db
class TestRedisTickDataSourceIter:
    """Tests for RedisTickDataSource.__iter__ with fakeredis."""

    def test_yields_tick_batches(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:1"

        ticks = [
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:00Z",
                "bid": "150.000",
                "ask": "150.010",
                "mid": "150.005",
            },
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:01Z",
                "bid": "150.100",
                "ask": "150.110",
                "mid": "150.105",
            },
        ]

        source = RedisTickDataSource(channel=channel, batch_size=10)

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_publish_ticks, args=(server, channel, ticks), daemon=True
            )
            publisher.start()

            all_ticks = []
            for batch in source:
                all_ticks.extend(batch)

            publisher.join(timeout=5)

        assert len(all_ticks) == 2
        assert all_ticks[0].instrument == "USD_JPY"
        assert all_ticks[0].bid == Decimal("150.000")
        assert all_ticks[1].bid == Decimal("150.100")

    def test_handles_eof(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:eof"

        source = RedisTickDataSource(channel=channel, batch_size=10)

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_publish_ticks, args=(server, channel, []), daemon=True
            )
            publisher.start()

            batches = list(source)
            publisher.join(timeout=5)

        assert batches == []

    def test_handles_stopped_signal(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:stop"

        source = RedisTickDataSource(channel=channel, batch_size=10)

        def publish_stop(srv, ch):
            client = fakeredis.FakeRedis(server=srv, decode_responses=True)
            time.sleep(0.05)
            client.publish(ch, json.dumps({"type": "stopped"}))
            client.close()

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(target=publish_stop, args=(server, channel), daemon=True)
            publisher.start()

            batches = list(source)
            publisher.join(timeout=5)

        assert batches == []

    def test_skips_invalid_ticks(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:invalid"

        messages = [
            {
                "type": "tick",
                "instrument": "",
                "timestamp": "2024-01-01T00:00:00Z",
                "bid": "1",
                "ask": "2",
            },  # empty instrument
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "bad-date",
                "bid": "1",
                "ask": "2",
            },  # bad timestamp
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:00Z",
                "bid": "not-a-number",
                "ask": "2",
            },  # bad price
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:00Z",
                "bid": "150.000",
                "ask": "150.010",
                "mid": "150.005",
            },  # valid
        ]

        source = RedisTickDataSource(channel=channel, batch_size=10)

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_publish_ticks, args=(server, channel, messages), daemon=True
            )
            publisher.start()

            all_ticks = []
            for batch in source:
                all_ticks.extend(batch)

            publisher.join(timeout=5)

        assert len(all_ticks) == 1
        assert all_ticks[0].instrument == "USD_JPY"

    def test_trigger_publisher_called(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:trigger"
        trigger = MagicMock()

        source = RedisTickDataSource(channel=channel, batch_size=10, trigger_publisher=trigger)

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_publish_ticks, args=(server, channel, []), daemon=True
            )
            publisher.start()

            list(source)
            publisher.join(timeout=5)

        trigger.assert_called_once()

    def test_batch_size_respected(self):
        server = fakeredis.FakeServer()
        channel = "test:backtest:ticks:batch"

        ticks = [
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": f"2024-01-01T00:00:{i:02d}Z",
                "bid": "150.000",
                "ask": "150.010",
                "mid": "150.005",
            }
            for i in range(5)
        ]

        source = RedisTickDataSource(channel=channel, batch_size=2)

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_publish_ticks, args=(server, channel, ticks), daemon=True
            )
            publisher.start()

            batches = []
            for batch in source:
                batches.append(len(batch))

            publisher.join(timeout=5)

        total = sum(batches)
        assert total == 5
        # At least one batch should have been yielded at size 2
        assert any(b == 2 for b in batches)
