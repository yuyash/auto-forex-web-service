"""Local market candle storage and backfill helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.market.models import MarketCandle, TickData


CANDLE_GRANULARITY_SECONDS: dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D": 86400,
}
DEFAULT_CANDLE_BATCH_SIZE = 1000


@dataclass(slots=True)
class CandleBuildStats:
    """Summary returned by candle backfill operations."""

    instrument: str
    granularity: str
    candles: int


@dataclass(slots=True)
class _MutableCandle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def update(self, value: Decimal, volume: int = 1) -> None:
        self.high = max(self.high, value)
        self.low = min(self.low, value)
        self.close = value
        self.volume += volume


class MarketCandleService:
    """Service for normalizing, loading, aggregating, and backfilling candles."""

    def normalize_granularity(self, value: Any) -> str:
        """Normalize a supported chart granularity token."""
        raw = str(value or "M1").strip().upper()
        if raw in {"", "RAW", "TICK", "1"}:
            return "M1"
        if raw.isdigit():
            raw = f"M{raw}"
        if raw in {"M60", "H1"}:
            return "H1"
        if raw in {"M240", "H4"}:
            return "H4"
        if raw in CANDLE_GRANULARITY_SECONDS:
            return raw
        raise ValidationError("granularity must be M1, M5, M15, M30, H1, H4, or D.")

    def load(
        self,
        *,
        instrument: str,
        granularity: str,
        since: datetime,
        until: datetime,
    ) -> list[dict[str, Any]]:
        """Load locally stored candles, aggregating stored M1 candles when needed."""
        normalized = self.normalize_granularity(granularity)
        direct = _load_candle_rows(
            instrument=instrument,
            granularity=normalized,
            since=since,
            until=until,
        )
        if direct or normalized == "M1":
            return direct

        m1_rows = _load_candle_rows(
            instrument=instrument,
            granularity="M1",
            since=since,
            until=until,
        )
        return _aggregate_serialized_candles(
            candles=m1_rows,
            granularity=normalized,
        )

    def backfill(
        self,
        *,
        instrument: str,
        granularity: str,
        since: datetime,
        until: datetime,
        batch_size: int = DEFAULT_CANDLE_BATCH_SIZE,
    ) -> CandleBuildStats:
        """Build and upsert candles from TickData or stored M1 candles."""
        normalized = self.normalize_granularity(granularity)
        if since >= until:
            raise ValidationError("since must be earlier than until.")

        candles = (
            _build_m1_candles_from_ticks(instrument=instrument, since=since, until=until)
            if normalized == "M1"
            else _build_higher_candles_from_m1(
                instrument=instrument,
                granularity=normalized,
                since=since,
                until=until,
            )
        )
        _upsert_market_candles(
            instrument=instrument,
            granularity=normalized,
            candles=candles,
            source="tick_data" if normalized == "M1" else "market_candles:M1",
            batch_size=batch_size,
        )
        return CandleBuildStats(
            instrument=instrument,
            granularity=normalized,
            candles=len(candles),
        )


market_candle_service = MarketCandleService()


def normalize_candle_granularity(value: Any) -> str:
    """Normalize a supported chart granularity token."""
    return market_candle_service.normalize_granularity(value)


def load_market_candles(
    *,
    instrument: str,
    granularity: str,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    """Load locally stored candles, aggregating stored M1 candles when needed."""
    return market_candle_service.load(
        instrument=instrument,
        granularity=granularity,
        since=since,
        until=until,
    )


def backfill_market_candles(
    *,
    instrument: str,
    granularity: str,
    since: datetime,
    until: datetime,
    batch_size: int = DEFAULT_CANDLE_BATCH_SIZE,
) -> CandleBuildStats:
    """Build and upsert candles from TickData or stored M1 candles."""
    return market_candle_service.backfill(
        instrument=instrument,
        granularity=granularity,
        since=since,
        until=until,
        batch_size=batch_size,
    )


def _load_candle_rows(
    *,
    instrument: str,
    granularity: str,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    if not instrument:
        return []
    return [
        _serialize_market_candle(row)
        for row in MarketCandle.objects.filter(
            instrument=instrument,
            granularity=granularity,
            timestamp__gte=since,
            timestamp__lte=until,
        )
        .order_by("timestamp")
        .values("timestamp", "open", "high", "low", "close", "volume")
    ]


def _build_m1_candles_from_ticks(
    *,
    instrument: str,
    since: datetime,
    until: datetime,
) -> list[_MutableCandle]:
    seconds = CANDLE_GRANULARITY_SECONDS["M1"]
    candles: dict[datetime, _MutableCandle] = {}
    rows = (
        TickData.objects.filter(
            instrument=instrument,
            timestamp__gte=since,
            timestamp__lt=until,
        )
        .order_by("timestamp")
        .values_list("timestamp", "mid")
        .iterator(chunk_size=5000)
    )
    for timestamp, mid in rows:
        value = Decimal(str(mid))
        bucket = _floor_datetime(timestamp, seconds)
        current = candles.get(bucket)
        if current is None:
            candles[bucket] = _MutableCandle(
                timestamp=bucket,
                open=value,
                high=value,
                low=value,
                close=value,
                volume=1,
            )
        else:
            current.update(value)
    return [candles[key] for key in sorted(candles)]


def _build_higher_candles_from_m1(
    *,
    instrument: str,
    granularity: str,
    since: datetime,
    until: datetime,
) -> list[_MutableCandle]:
    m1_rows = (
        MarketCandle.objects.filter(
            instrument=instrument,
            granularity="M1",
            timestamp__gte=since,
            timestamp__lt=until,
        )
        .order_by("timestamp")
        .values_list("timestamp", "open", "high", "low", "close", "volume")
        .iterator(chunk_size=5000)
    )
    seconds = CANDLE_GRANULARITY_SECONDS[granularity]
    buckets: dict[datetime, _MutableCandle] = {}
    for timestamp, open_price, high, low, close, volume in m1_rows:
        bucket = _floor_datetime(timestamp, seconds)
        current = buckets.get(bucket)
        if current is None:
            buckets[bucket] = _MutableCandle(
                timestamp=bucket,
                open=Decimal(str(open_price)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=int(volume or 0),
            )
        else:
            current.high = max(current.high, Decimal(str(high)))
            current.low = min(current.low, Decimal(str(low)))
            current.close = Decimal(str(close))
            current.volume += int(volume or 0)
    return [buckets[key] for key in sorted(buckets)]


def _aggregate_serialized_candles(
    *,
    candles: Iterable[dict[str, Any]],
    granularity: str,
) -> list[dict[str, Any]]:
    seconds = CANDLE_GRANULARITY_SECONDS[granularity]
    buckets: dict[int, dict[str, Any]] = {}
    for candle in candles:
        time_value = int(candle["time"])
        bucket = time_value // seconds * seconds
        current = buckets.get(bucket)
        if current is None:
            buckets[bucket] = {
                "time": bucket,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": int(candle.get("volume") or 0),
            }
        else:
            current["high"] = max(float(current["high"]), float(candle["high"]))
            current["low"] = min(float(current["low"]), float(candle["low"]))
            current["close"] = float(candle["close"])
            current["volume"] = int(current.get("volume") or 0) + int(candle.get("volume") or 0)
    return [buckets[key] for key in sorted(buckets)]


def _upsert_market_candles(
    *,
    instrument: str,
    granularity: str,
    candles: list[_MutableCandle],
    source: str,
    batch_size: int,
) -> None:
    if not candles:
        return

    objs = [
        MarketCandle(
            instrument=instrument,
            granularity=granularity,
            timestamp=candle.timestamp,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            source=source,
        )
        for candle in candles
    ]
    with transaction.atomic():
        MarketCandle.objects.bulk_create(
            objs,
            batch_size=batch_size,
            update_conflicts=True,
            update_fields=["open", "high", "low", "close", "volume", "source", "updated_at"],
            unique_fields=["instrument", "granularity", "timestamp"],
        )


def _serialize_market_candle(row: dict[str, Any]) -> dict[str, Any]:
    timestamp = row["timestamp"]
    if timezone.is_naive(timestamp):
        timestamp = timezone.make_aware(timestamp, UTC)
    return {
        "time": int(timestamp.timestamp()),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": int(row.get("volume") or 0),
    }


def _floor_datetime(value: datetime, seconds: int) -> datetime:
    aware = value if timezone.is_aware(value) else timezone.make_aware(value, UTC)
    timestamp = int(aware.astimezone(UTC).timestamp())
    return datetime.fromtimestamp(timestamp // seconds * seconds, tz=UTC)
