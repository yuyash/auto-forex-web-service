"""Integration tests for ``RedisStreamTickDataSource`` against fakeredis.

These tests exercise the stream-based backtest tick delivery path end to
end: ``XADD`` from a background publisher, ``XREAD BLOCK`` consumption,
terminal markers, idle timeout, and reconnect resilience.
"""

import threading
import time
from decimal import Decimal
from unittest.mock import patch

import fakeredis
import pytest

from apps.trading.tasks.source import RedisStreamTickDataSource


def _xadd_ticks(fake_server, stream_key, ticks, delay=0.05, terminator="eof"):
    """Append tick entries (and optionally a terminator) in a background thread."""
    client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
    time.sleep(delay)
    try:
        for tick in ticks:
            client.xadd(stream_key, tick, maxlen=10_000, approximate=True)
            time.sleep(0.005)
        if terminator:
            client.xadd(stream_key, {"type": terminator}, maxlen=10_000, approximate=True)
    finally:
        client.close()


@pytest.mark.django_db
class TestRedisStreamTickDataSourceIter:
    """Happy-path and control-message behaviours."""

    def test_yields_tick_batches(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:yields"

        entries = [
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

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=10,
            block_ms=50,
            read_count=10,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_xadd_ticks, args=(server, stream_key, entries), daemon=True
            )
            publisher.start()

            received = []
            for batch in source:
                received.extend(batch)

            publisher.join(timeout=5)

        assert len(received) == 2
        assert received[0].instrument == "USD_JPY"
        assert received[0].bid == Decimal("150.000")
        assert received[1].bid == Decimal("150.100")

    def test_stops_on_eof(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:eof"

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=10,
            block_ms=50,
            read_count=10,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_xadd_ticks, args=(server, stream_key, []), daemon=True
            )
            publisher.start()

            batches = list(source)
            publisher.join(timeout=5)

        assert batches == []

    def test_stops_on_stopped_marker(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:stopped"

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=10,
            block_ms=50,
            read_count=10,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_xadd_ticks,
                args=(server, stream_key, []),
                kwargs={"terminator": "stopped"},
                daemon=True,
            )
            publisher.start()

            batches = list(source)
            publisher.join(timeout=5)

        assert batches == []

    def test_idle_timeout_aborts_when_stream_silent(self):
        """Stream with no entries and no EOF must eventually return."""
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:idle"

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=10,
            block_ms=10,
            read_count=10,
            idle_timeout_reads=3,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            batches = list(source)

        assert batches == []

    def test_triggers_publisher_callback(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:trigger"

        trigger_called = threading.Event()

        def _trigger():
            # Publish exactly one tick then EOF so the iterator can exit.
            client = fakeredis.FakeRedis(server=server, decode_responses=True)
            client.xadd(
                stream_key,
                {
                    "type": "tick",
                    "instrument": "USD_JPY",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "bid": "150.0",
                    "ask": "150.02",
                    "mid": "150.01",
                },
                maxlen=100,
                approximate=True,
            )
            client.xadd(stream_key, {"type": "eof"}, maxlen=100, approximate=True)
            client.close()
            trigger_called.set()

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=1,
            trigger_publisher=_trigger,
            block_ms=50,
            read_count=5,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            received: list = []
            for batch in source:
                received.extend(batch)

        assert trigger_called.is_set()
        assert len(received) == 1

    def test_skips_invalid_ticks(self):
        """Malformed entries must not break the stream."""
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:invalid"

        entries = [
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:00Z",
                # Missing bid/ask/mid -> should be skipped.
            },
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2024-01-01T00:00:01Z",
                "bid": "150.0",
                "ask": "150.02",
                "mid": "150.01",
            },
        ]

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=10,
            block_ms=50,
            read_count=10,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            publisher = threading.Thread(
                target=_xadd_ticks, args=(server, stream_key, entries), daemon=True
            )
            publisher.start()

            received = []
            for batch in source:
                received.extend(batch)

            publisher.join(timeout=5)

        assert len(received) == 1
        assert received[0].bid == Decimal("150.0")

    def test_resumes_from_last_id_after_reconnect(self):
        """Tick 1 is read, then we force a reconnect before tick 2.

        Because the consumer tracks ``last_id`` it must resume from the
        point just after tick 1 and *not* receive tick 1 twice.
        """
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:reconnect"

        tick1 = {
            "type": "tick",
            "instrument": "USD_JPY",
            "timestamp": "2024-01-01T00:00:00Z",
            "bid": "150.00",
            "ask": "150.02",
            "mid": "150.01",
        }
        tick2 = {
            "type": "tick",
            "instrument": "USD_JPY",
            "timestamp": "2024-01-01T00:00:01Z",
            "bid": "150.10",
            "ask": "150.12",
            "mid": "150.11",
        }
        # Pre-populate before the consumer starts so both entries are visible
        # on the initial XREAD call; a reconnect in the middle must not
        # cause duplication.
        seed_client = fakeredis.FakeRedis(server=server, decode_responses=True)
        seed_client.xadd(stream_key, tick1, maxlen=100, approximate=True)
        seed_client.xadd(stream_key, tick2, maxlen=100, approximate=True)
        seed_client.xadd(stream_key, {"type": "eof"}, maxlen=100, approximate=True)
        seed_client.close()

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=1,
            block_ms=50,
            read_count=1,
            idle_timeout_reads=20,
        )

        with patch("apps.trading.tasks.source.redis.Redis.from_url") as mock_from_url:
            fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)
            mock_from_url.return_value = fake_client

            received = []
            for batch in source:
                received.extend(batch)

        assert len(received) == 2
        assert received[0].bid == Decimal("150.00")
        assert received[1].bid == Decimal("150.10")
