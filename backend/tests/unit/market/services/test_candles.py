"""Tests for local market candle backfill helpers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.market.models import MarketCandle, TickData
from apps.market.services.candles import backfill_market_candles, load_market_candles


@pytest.mark.django_db
def test_backfill_market_candles_builds_m1_from_ticks():
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    TickData.objects.bulk_create(
        [
            TickData(
                instrument="USD_JPY",
                timestamp=base,
                bid=Decimal("156.00"),
                ask=Decimal("156.02"),
                mid=Decimal("156.01"),
            ),
            TickData(
                instrument="USD_JPY",
                timestamp=base + timedelta(seconds=20),
                bid=Decimal("156.04"),
                ask=Decimal("156.06"),
                mid=Decimal("156.05"),
            ),
            TickData(
                instrument="USD_JPY",
                timestamp=base + timedelta(minutes=1),
                bid=Decimal("156.02"),
                ask=Decimal("156.04"),
                mid=Decimal("156.03"),
            ),
        ]
    )

    stats = backfill_market_candles(
        instrument="USD_JPY",
        granularity="M1",
        since=base,
        until=base + timedelta(minutes=2),
    )

    assert stats.candles == 2
    candles = list(MarketCandle.objects.order_by("timestamp"))
    assert candles[0].open == Decimal("156.0100000000")
    assert candles[0].high == Decimal("156.0500000000")
    assert candles[0].low == Decimal("156.0100000000")
    assert candles[0].close == Decimal("156.0500000000")
    assert candles[0].volume == 2


@pytest.mark.django_db
def test_load_market_candles_aggregates_from_stored_m1():
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    for index, close in enumerate(["156.01", "156.03", "156.02", "156.06", "156.05"]):
        MarketCandle.objects.create(
            instrument="USD_JPY",
            granularity="M1",
            timestamp=base + timedelta(minutes=index),
            open=Decimal("156.00"),
            high=Decimal(close) + Decimal("0.01"),
            low=Decimal(close) - Decimal("0.01"),
            close=Decimal(close),
            volume=1,
        )

    candles = load_market_candles(
        instrument="USD_JPY",
        granularity="M5",
        since=base,
        until=base + timedelta(minutes=5),
    )

    assert candles == [
        {
            "time": int(base.timestamp()),
            "open": 156.0,
            "high": 156.07,
            "low": 156.0,
            "close": 156.05,
            "volume": 5,
        }
    ]
