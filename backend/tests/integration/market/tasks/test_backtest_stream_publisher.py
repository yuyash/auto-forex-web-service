"""Integration tests for the stream-based backtest publisher.

Validates the three behaviours that the earlier implementations could
not guarantee:

1. Ticks are written to a per-request Redis Stream (not Pub/Sub), so
   nothing is lost when the subscriber lags.
2. Before any XADD the publisher creates a consumer group so the
   subscriber can use ``XREADGROUP``/``XACK`` and the publisher can
   measure real consumer lag via ``XPENDING``.
3. Backpressure is driven by ``XPENDING`` (unACKed count), not
   ``XLEN``: the publisher pauses only while the consumer is actually
   behind, and resumes as soon as ACKs flow back.  An ``XLEN`` based
   implementation would never resume (XLEN doesn't decrease on
   read/ACK, only on XDEL/XTRIM).
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from django.contrib.auth import get_user_model

from apps.market.models import TickData
from apps.market.tasks.backtest import BacktestTickPublisherRunner
from apps.market.tasks.base import backtest_stream_key_for_request
from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, StrategyConfiguration


def _make_task(**overrides) -> BacktestTask:
    User = get_user_model()
    user = User.objects.create_user(  # type: ignore[attr-defined]
        email=f"{overrides.get('suffix', 'stream')}@example.com",
        password="testpass123",
        username=f"streamuser-{overrides.get('suffix', 'x')}",
    )
    config = StrategyConfiguration.objects.create(
        user=user,
        name=f"Config {overrides.get('suffix', 'x')}",
        strategy_type="floor",
        parameters={"instrument": "USD_JPY"},
    )
    return BacktestTask.objects.create(
        name=overrides.get("name", f"Stream Backtest {overrides.get('suffix', 'x')}"),
        user=user,
        config=config,
        instrument="USD_JPY",
        start_time=overrides.get("start", datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)),
        end_time=overrides.get("end", datetime(2024, 1, 1, 12, 0, 30, tzinfo=UTC)),
        initial_balance=Decimal("10000.00"),
        status=TaskStatus.RUNNING,
    )


def _seed_ticks(count: int, *, start: datetime | None = None) -> None:
    start = start or datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    from datetime import timedelta

    for i in range(count):
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=start + timedelta(seconds=i),
            bid=Decimal(f"{150 + i * 0.01:.5f}"),
            ask=Decimal(f"{150.02 + i * 0.01:.5f}"),
            mid=Decimal(f"{150.01 + i * 0.01:.5f}"),
        )


@pytest.mark.django_db
class TestBacktestStreamPublisher:
    """Publisher writes to a per-request stream and creates the group."""

    def test_ticks_are_written_to_stream(self, settings) -> None:
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0  # disable backpressure

        task = _make_task(suffix="write")
        _seed_ticks(5, start=task.start_time)

        fake_server = fakeredis.FakeServer()
        fake_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
            )

        stream_key = backtest_stream_key_for_request(str(task.pk))
        entries = fake_client.xrange(stream_key)
        assert entries, "Publisher should have written entries to the stream"

        tick_entries = [e for e in entries if e[1].get("type") == "tick"]
        eof_entries = [e for e in entries if e[1].get("type") == "eof"]
        assert len(tick_entries) == 5
        assert len(eof_entries) == 1
        assert tick_entries[0][1]["instrument"] == "USD_JPY"

    def test_spread_filter_skips_wide_spread_ticks(self, settings) -> None:
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0

        task = _make_task(suffix="spread")
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=task.start_time,
            bid=Decimal("150.000"),
            ask=Decimal("150.020"),
            mid=Decimal("150.010"),
        )
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=task.start_time.replace(second=1),
            bid=Decimal("150.000"),
            ask=Decimal("150.500"),
            mid=Decimal("150.250"),
        )
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=task.start_time.replace(second=2),
            bid=Decimal("150.010"),
            ask=Decimal("150.030"),
            mid=Decimal("150.020"),
        )

        fake_server = fakeredis.FakeServer()
        fake_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
                pip_size="0.01",
                spread_filter_enabled=True,
                max_spread_pips="5",
            )

        stream_key = backtest_stream_key_for_request(str(task.pk))
        entries = fake_client.xrange(stream_key)
        tick_entries = [e for e in entries if e[1].get("type") == "tick"]
        eof_entries = [e for e in entries if e[1].get("type") == "eof"]
        assert len(tick_entries) == 2
        assert len(eof_entries) == 1
        assert eof_entries[0][1]["count"] == "2"

    def test_publisher_creates_consumer_group(self, settings) -> None:
        """The consumer group must exist after ``run`` so XREADGROUP works."""
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0
        settings.MARKET_BACKTEST_STREAM_CONSUMER_GROUP = "backtest"

        task = _make_task(suffix="grp")
        _seed_ticks(1, start=task.start_time)

        fake_server = fakeredis.FakeServer()
        fake_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
            )

        stream_key = backtest_stream_key_for_request(str(task.pk))
        groups = fake_client.xinfo_groups(stream_key)
        assert any(g.get("name") in ("backtest", b"backtest") for g in groups)

    def test_backpressure_pauses_on_lag_then_resumes_on_drain(self, settings) -> None:
        """Backpressure is driven by XINFO GROUPS lag + pending, not XLEN.

        We rig ``XINFO GROUPS`` to report a large combined lag for the
        first few checks, then to report the queue draining to
        simulate the consumer catching up.  The publisher must pause
        and subsequently resume.  Unlike the old XPENDING-only guard,
        this signal also accounts for entries the subscriber hasn't
        even read yet (``lag``), so a subscriber that stalls before
        its first ``XREADGROUP`` still applies back-pressure — that
        is the failure mode that previously produced silent MAXLEN
        trimming of undelivered ticks.
        """
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 10_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 100
        settings.MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK = 50
        settings.MARKET_BACKTEST_BACKPRESSURE_SLEEP_SECONDS = 0.01

        task = _make_task(suffix="bp")
        _seed_ticks(3, start=task.start_time)

        # First three xinfo_groups calls: lag=200 (paused). Then lag
        # drops below low_watermark so the publisher resumes.
        lag_values = [200, 200, 200, 30, 30, 0, 0, 0, 0, 0, 0]

        def fake_xinfo_groups(_stream_key):
            val = lag_values.pop(0) if lag_values else 0
            return [{"name": "backtest", "lag": val, "pending": 0}]

        xadd_calls: list = []

        def fake_xadd(stream_key, payload, maxlen=None, approximate=None):
            xadd_calls.append((stream_key, dict(payload), maxlen, approximate))
            return b"1-0"

        fake_client = MagicMock()
        fake_client.xinfo_groups.side_effect = fake_xinfo_groups
        fake_client.xpending.return_value = {"pending": 0}
        fake_client.xadd.side_effect = fake_xadd
        fake_client.delete.return_value = 0
        fake_client.xgroup_create.return_value = True

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
            )

        tick_calls = [c for c in xadd_calls if c[1].get("type") == "tick"]
        eof_calls = [c for c in xadd_calls if c[1].get("type") == "eof"]
        assert len(tick_calls) == 3, (
            "Publisher must produce every tick once the consumer catches up"
        )
        assert len(eof_calls) == 1

        # XINFO GROUPS is the primary signal now — assert we consulted
        # it during the run (multiple times because of the backpressure
        # loop).
        assert fake_client.xinfo_groups.call_count >= 3

    def test_publisher_uses_maxlen_trimming(self, settings) -> None:
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 123
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0

        task = _make_task(suffix="maxlen")
        _seed_ticks(2, start=task.start_time)

        fake_client = MagicMock()
        fake_client.xadd.return_value = b"1-0"
        fake_client.xpending.return_value = {"pending": 0}
        fake_client.delete.return_value = 0
        fake_client.xgroup_create.return_value = True

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
            )

        tick_xadd = [
            call for call in fake_client.xadd.call_args_list if call.args[1].get("type") == "tick"
        ]
        assert tick_xadd, "Expected XADD calls for ticks"
        for call in tick_xadd:
            assert call.kwargs.get("maxlen") == 123
            assert call.kwargs.get("approximate") is True

    def test_backpressure_check_interval_is_headroom_bounded(self) -> None:
        runner = BacktestTickPublisherRunner()

        assert (
            runner._backpressure_check_interval(
                stream_maxlen=200_000,
                high_watermark=100_000,
                configured_interval=100,
            )
            == 100
        )
        assert (
            runner._backpressure_check_interval(
                stream_maxlen=1_000,
                high_watermark=900,
                configured_interval=1_000,
            )
            == 50
        )
        assert (
            runner._backpressure_check_interval(
                stream_maxlen=1_000,
                high_watermark=1_000,
                configured_interval=100,
            )
            == 1
        )

    def test_should_check_backpressure_only_on_interval_or_while_waiting(self) -> None:
        runner = BacktestTickPublisherRunner()

        assert runner._should_check_backpressure(
            published=0,
            check_interval=100,
            already_waiting=False,
        )
        assert not runner._should_check_backpressure(
            published=99,
            check_interval=100,
            already_waiting=False,
        )
        assert runner._should_check_backpressure(
            published=100,
            check_interval=100,
            already_waiting=False,
        )
        assert runner._should_check_backpressure(
            published=99,
            check_interval=100,
            already_waiting=True,
        )


@pytest.mark.django_db
class TestBacktestStreamPublisherExecutionIsolation:
    """Execution-scoped stream keys and fresh consumer groups prevent a
    new run from inheriting leftover entries from a previous execution."""

    def test_execution_scoped_stream_receives_all_ticks(self, settings) -> None:
        """Writing with an ``execution_id`` produces an isolated stream."""
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0

        task = _make_task(suffix="exec")
        _seed_ticks(3, start=task.start_time)

        fake_server = fakeredis.FakeServer()
        fake_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
        execution_id = "execution-aaa"

        runner = BacktestTickPublisherRunner()
        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
                execution_id=execution_id,
            )

        scoped_key = backtest_stream_key_for_request(str(task.pk), execution_id)
        legacy_key = backtest_stream_key_for_request(str(task.pk))

        entries = fake_client.xrange(scoped_key)
        assert entries, "Execution-scoped stream should contain entries"
        assert not fake_client.exists(legacy_key), (
            "Legacy task-id-only stream should remain empty when execution_id is provided"
        )

    def test_publisher_starts_group_after_prior_entries_for_same_execution(self, settings) -> None:
        """A crashed prior attempt left leftover entries — the next run
        must not deliver them to the new consumer group."""
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0

        task = _make_task(suffix="wipe")
        _seed_ticks(2, start=task.start_time)

        fake_server = fakeredis.FakeServer()
        fake_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)
        execution_id = "execution-bbb"
        stream_key = backtest_stream_key_for_request(str(task.pk), execution_id)

        # Simulate a stale entry from a previous crashed attempt.
        fake_client.xadd(
            stream_key,
            {
                "type": "tick",
                "instrument": "USD_JPY",
                "timestamp": "2099-01-01T00:00:00Z",
                "bid": "99.99",
                "ask": "99.99",
                "mid": "99.99",
            },
        )
        assert fake_client.xlen(stream_key) == 1

        runner = BacktestTickPublisherRunner()
        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
                execution_id=execution_id,
            )

        entries = fake_client.xrange(stream_key)
        assert len(entries) == 4
        assert any(fields.get("timestamp", "").startswith("2099") for _id, fields in entries)

        delivered = fake_client.xreadgroup(
            "backtest",
            "consumer-1",
            {stream_key: ">"},
            count=10,
        )
        delivered_entries = delivered[0][1]
        # Only the 2 DB ticks + 1 EOF are delivered to the fresh group; the
        # stale tick remains in Redis but is behind the group's start offset.
        assert len(delivered_entries) == 3
        for _id, fields in delivered_entries:
            ts = fields.get("timestamp", "")
            assert not ts.startswith("2099"), f"Stale entry was delivered: {fields}"
