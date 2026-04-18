"""Integration tests for ``RedisStreamTickDataSource`` against fakeredis.

These tests exercise the consumer-group-based backtest tick delivery
path: ``XADD`` into a seeded stream, ``XREADGROUP`` consumption with
``XACK``, terminal markers, idle timeout, and reconnect resilience.

Implementation note: fakeredis does not deliver cross-thread stream
notifications for ``XREADGROUP`` (blocking reads ignore XADDs from
other connections on the same fake server).  These tests therefore
seed the stream with all expected entries **before** the subscriber
iterates, which faithfully exercises the consumer-group semantics
without relying on threading.
"""

from decimal import Decimal
from unittest.mock import patch

import fakeredis
import pytest

from apps.trading.tasks.source import RedisStreamTickDataSource


def _seed_group(fake_server, stream_key: str, group: str = "backtest") -> None:
    """Create the consumer group at the stream tip."""
    client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
    try:
        client.xgroup_create(stream_key, group, id="$", mkstream=True)
    except Exception:
        pass
    finally:
        client.close()


def _add_entries(fake_server, stream_key: str, entries: list[dict]) -> None:
    """Write entries directly to the stream."""
    client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
    try:
        for entry in entries:
            client.xadd(stream_key, entry, maxlen=10_000, approximate=True)
    finally:
        client.close()


@pytest.mark.django_db
class TestRedisStreamTickDataSourceIter:
    """Happy-path and control-message behaviours."""

    def test_yields_tick_batches(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:yields"
        _seed_group(server, stream_key)
        _add_entries(
            server,
            stream_key,
            [
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
                {"type": "eof"},
            ],
        )

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

            received = []
            for batch in source:
                received.extend(batch)

        assert len(received) == 2
        assert received[0].instrument == "USD_JPY"
        assert received[0].bid == Decimal("150.000")
        assert received[1].bid == Decimal("150.100")

    def test_acks_entries_as_they_are_consumed(self):
        """Every consumed entry must be XACKed so ``XPENDING`` reflects
        true lag — this is the hook the publisher uses for backpressure."""
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:ack"
        _seed_group(server, stream_key)
        _add_entries(
            server,
            stream_key,
            [
                {
                    "type": "tick",
                    "instrument": "USD_JPY",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "bid": "150.000",
                    "ask": "150.010",
                    "mid": "150.005",
                },
                {"type": "eof"},
            ],
        )

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

            for _batch in source:
                pass

            info = fake_client.xpending(stream_key, "backtest")

        assert isinstance(info, dict)
        assert info.get("pending", 0) == 0

    def test_stops_on_eof(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:eof"
        _seed_group(server, stream_key)
        _add_entries(server, stream_key, [{"type": "eof"}])

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

            batches = list(source)

        assert batches == []

    def test_stops_on_stopped_marker(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:stopped"
        _seed_group(server, stream_key)
        _add_entries(server, stream_key, [{"type": "stopped"}])

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

            batches = list(source)

        assert batches == []

    def test_idle_timeout_aborts_when_stream_silent(self):
        """Empty stream (no publisher activity) must eventually return.

        The stream is empty, so ``last-generated-id`` is effectively
        ``0-0`` — the consumer is trivially caught up and the idle
        counter advances normally.
        """
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:idle"
        _seed_group(server, stream_key)

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

    def test_idle_timeout_does_not_fire_while_consumer_is_behind(self):
        """Regression test for the backpressure/idle-timeout deadlock.

        Simulate the state the consumer was in when the bug fired:
          - publisher has added lots of entries (last-generated-id is
            far ahead)
          - consumer is still catching up — it has read some entries
            but not all of them

        An ``XLEN``-based or blind-empty-read idle timer would falsely
        decide the stream is done and exit prematurely.  Our design
        checks ``last-generated-id`` on every empty read and only
        counts the read toward idle timeout when the consumer has
        caught up.

        We verify the new logic directly by constructing a minimal
        source, manually advancing its state, and calling the caught-up
        predicate.
        """
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:notbehind"
        _seed_group(server, stream_key)
        _add_entries(
            server,
            stream_key,
            [
                {
                    "type": "tick",
                    "instrument": "USD_JPY",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "bid": "150.0",
                    "ask": "150.02",
                    "mid": "150.01",
                },
                {
                    "type": "tick",
                    "instrument": "USD_JPY",
                    "timestamp": "2024-01-01T00:00:01Z",
                    "bid": "150.1",
                    "ask": "150.12",
                    "mid": "150.11",
                },
            ],
        )

        source = RedisStreamTickDataSource(
            stream_key=stream_key,
            batch_size=1,
            block_ms=50,
            read_count=1,
            idle_timeout_reads=20,
        )
        source.client = fakeredis.FakeRedis(server=server, decode_responses=True)
        # Consumer has "seen" nothing yet — it must not be flagged as
        # caught up even though XREADGROUP returned no entries on the
        # (hypothetical) first call.
        source._last_seen_id = "0-0"
        assert source._consumer_caught_up_with_publisher() is False

        # Pretend the consumer has now seen the last entry the publisher
        # has added.  It should be considered caught up.
        info = source.client.xinfo_stream(stream_key)
        last_entry = info.get("last-entry")
        assert last_entry
        last_id = last_entry[0] if isinstance(last_entry, (list, tuple)) else None
        assert last_id
        source._last_seen_id = last_id
        assert source._consumer_caught_up_with_publisher() is True

    def test_triggers_publisher_callback(self):
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:trigger"
        _seed_group(server, stream_key)

        trigger_called = {"count": 0}

        def _trigger():
            # Simulate what the real publisher does: create the consumer
            # group (already done above) and XADD into the stream.  The
            # callback runs synchronously so entries are ready for the
            # very first XREADGROUP.
            trigger_called["count"] += 1
            client = fakeredis.FakeRedis(server=server, decode_responses=True)
            try:
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
            finally:
                client.close()

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

            # Also force the celery-always-eager branch to False so the
            # trigger runs synchronously (more deterministic under
            # fakeredis).
            from celery import current_app

            current_app.conf.task_always_eager = False

            received: list = []
            for batch in source:
                received.extend(batch)

        assert trigger_called["count"] == 1
        assert len(received) == 1

    def test_skips_invalid_ticks(self):
        """Malformed entries must not break the stream."""
        server = fakeredis.FakeServer()
        stream_key = "test:backtest:stream:invalid"
        _seed_group(server, stream_key)
        _add_entries(
            server,
            stream_key,
            [
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
                {"type": "eof"},
            ],
        )

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

            received = []
            for batch in source:
                received.extend(batch)

        assert len(received) == 1
        assert received[0].bid == Decimal("150.0")
