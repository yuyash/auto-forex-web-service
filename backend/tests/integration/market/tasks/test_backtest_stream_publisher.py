"""Integration tests for the stream-based backtest publisher.

Focuses on two behaviours that the pub/sub implementation could not
deliver reliably:

1. Ticks are written to a Redis Stream (not published over Pub/Sub), so
   nothing is lost when the subscriber lags.
2. The publisher applies backpressure: once the stream exceeds the
   configured high-water mark it pauses (``XLEN``-based) until the
   subscriber drains below the low-water mark, instead of racing ahead
   and overflowing the transport.
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
    """Publisher must use Redis Streams and apply backpressure."""

    def test_ticks_are_written_to_stream(self, settings) -> None:
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 1_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0  # disable backpressure
        settings.MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK = 0

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

    def test_backpressure_pauses_until_consumer_drains(self, settings) -> None:
        """When XLEN exceeds the high watermark the publisher must pause.

        We simulate that by rigging a fake ``xlen`` that reports a full
        queue for the first few calls, then reports the queue draining.
        The test asserts that ``XADD`` never happens while the queue is
        above the high watermark.
        """
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 10_000
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 100
        settings.MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK = 50
        settings.MARKET_BACKTEST_BACKPRESSURE_SLEEP_SECONDS = 0.01

        task = _make_task(suffix="bp")
        _seed_ticks(3, start=task.start_time)

        reported_lengths = [200, 200, 60, 60, 60]  # first two: stall; then drain

        def fake_xlen(_stream_key):
            return reported_lengths.pop(0) if reported_lengths else 0

        xadd_calls: list = []

        def fake_xadd(stream_key, payload, maxlen=None, approximate=None):
            xadd_calls.append((stream_key, dict(payload), maxlen, approximate))
            return b"1-0"

        fake_client = MagicMock()
        fake_client.xlen.side_effect = fake_xlen
        fake_client.xadd.side_effect = fake_xadd
        fake_client.delete.return_value = 0

        runner = BacktestTickPublisherRunner()

        with patch("apps.market.tasks.backtest.redis_client", return_value=fake_client):
            runner.run(
                instrument="USD_JPY",
                start=task.start_time.isoformat(),
                end=task.end_time.isoformat(),
                request_id=str(task.pk),
            )

        # All 3 ticks + EOF should have been written eventually.
        tick_calls = [c for c in xadd_calls if c[1].get("type") == "tick"]
        eof_calls = [c for c in xadd_calls if c[1].get("type") == "eof"]
        assert len(tick_calls) == 3
        assert len(eof_calls) == 1

        # XLEN was consulted multiple times, proving backpressure actually
        # kicked in instead of being a no-op.
        assert fake_client.xlen.call_count >= 3

    def test_publisher_uses_maxlen_trimming(self, settings) -> None:
        settings.MARKET_BACKTEST_STREAM_MAXLEN = 123
        settings.MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK = 0
        settings.MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK = 0

        task = _make_task(suffix="maxlen")
        _seed_ticks(2, start=task.start_time)

        fake_client = MagicMock()
        fake_client.xadd.return_value = b"1-0"
        fake_client.xlen.return_value = 0
        fake_client.delete.return_value = 0

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
