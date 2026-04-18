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

    def test_backpressure_pauses_on_pending_then_resumes_on_acks(self, settings) -> None:
        """Backpressure is driven by XPENDING, not XLEN.

        We rig XPENDING to report a full queue for the first few
        checks, then to report the queue draining as if the consumer
        ACKed.  The publisher must pause and subsequently resume.  If
        the implementation still used XLEN it would never resume
        because XLEN does not shrink on ACK.
        """
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 10_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 100
        settings.MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK = 50
        settings.MARKET_BACKTEST_BACKPRESSURE_SLEEP_SECONDS = 0.01

        task = _make_task(suffix="bp")
        _seed_ticks(3, start=task.start_time)

        # First two xpending calls: pending=200 (paused).  Then pending
        # drops below low_watermark so the publisher resumes.
        pending_values = [200, 200, 200, 30, 30, 0, 0, 0, 0, 0, 0]

        def fake_xpending(_stream_key, _group):
            val = pending_values.pop(0) if pending_values else 0
            return {"pending": val, "min": None, "max": None, "consumers": []}

        xadd_calls: list = []

        def fake_xadd(stream_key, payload, maxlen=None, approximate=None):
            xadd_calls.append((stream_key, dict(payload), maxlen, approximate))
            return b"1-0"

        fake_client = MagicMock()
        fake_client.xpending.side_effect = fake_xpending
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

        # XPENDING is the mechanism we rely on — assert we actually
        # consulted it during the run (multiple times because of the
        # backpressure loop).
        assert fake_client.xpending.call_count >= 3

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
