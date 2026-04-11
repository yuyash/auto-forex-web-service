"""Helpers for querying aggregated historical ticks for backtests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median

from django.db import connection

from apps.market.models import TickData


@dataclass(frozen=True, slots=True)
class BacktestTickRow:
    """Normalized tick row returned for backtest replay."""

    timestamp: datetime
    bid: Decimal
    ask: Decimal
    mid: Decimal


_INTERVAL_SQL_BY_GRANULARITY: dict[str, str] = {
    "1s": "1 second",
    "10s": "10 seconds",
    "15s": "15 seconds",
    "30s": "30 seconds",
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "30m": "30 minutes",
    "1h": "1 hour",
}

_INTERVAL_SECONDS_BY_GRANULARITY: dict[str, int] = {
    "1s": 1,
    "10s": 10,
    "15s": 15,
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
}


def iter_aggregated_backtest_ticks(
    *,
    instrument: str,
    start_dt: datetime,
    end_dt: datetime,
    granularity: str,
    mode: str,
    batch_size: int,
) -> Iterator[BacktestTickRow]:
    """Yield aggregated backtest tick rows from PostgreSQL."""
    if connection.vendor != "postgresql":
        yield from _iter_aggregated_backtest_ticks_python(
            instrument=instrument,
            start_dt=start_dt,
            end_dt=end_dt,
            granularity=granularity,
            mode=mode,
            batch_size=batch_size,
        )
        return

    interval_sql = _INTERVAL_SQL_BY_GRANULARITY[granularity]
    sql = _build_aggregation_sql(mode=mode)
    with connection.cursor() as cursor:
        cursor.execute(sql, [interval_sql, instrument, start_dt, end_dt])
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                return
            for timestamp, bid, ask, mid in rows:
                yield BacktestTickRow(
                    timestamp=timestamp,
                    bid=Decimal(str(bid)),
                    ask=Decimal(str(ask)),
                    mid=Decimal(str(mid)),
                )


def _build_aggregation_sql(*, mode: str) -> str:
    filtered_cte = """
        WITH filtered AS (
            SELECT
                date_bin(%s::interval, timestamp, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS bucket,
                timestamp,
                bid,
                ask,
                mid
            FROM tick_data
            WHERE instrument = %s
              AND timestamp >= %s
              AND timestamp <= %s
        )
    """

    if mode == "average":
        average_sql = """
            SELECT
                bucket AS timestamp,
                AVG(bid) AS bid,
                AVG(ask) AS ask,
                AVG(mid) AS mid
            FROM filtered
            GROUP BY bucket
            ORDER BY bucket
            """  # nosec B608
        return filtered_cte + average_sql

    if mode == "median":
        median_sql = """
            SELECT
                bucket AS timestamp,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY bid) AS bid,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY ask) AS ask,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY mid) AS mid
            FROM filtered
            GROUP BY bucket
            ORDER BY bucket
            """  # nosec B608
        return filtered_cte + median_sql

    ordering = "ASC" if mode == "first" else "DESC"
    ranked_sql = f"""
        , ranked AS (
            SELECT
                bucket,
                timestamp,
                bid,
                ask,
                mid,
                ROW_NUMBER() OVER (
                    PARTITION BY bucket
                    ORDER BY timestamp {ordering}
                ) AS row_num
            FROM filtered
        )
        SELECT
            bucket AS timestamp,
            bid,
            ask,
            mid
        FROM ranked
        WHERE row_num = 1
        ORDER BY bucket
        """  # nosec B608
    return filtered_cte + ranked_sql


def _iter_aggregated_backtest_ticks_python(
    *,
    instrument: str,
    start_dt: datetime,
    end_dt: datetime,
    granularity: str,
    mode: str,
    batch_size: int,
) -> Iterator[BacktestTickRow]:
    bucket_seconds = _INTERVAL_SECONDS_BY_GRANULARITY[granularity]
    qs = (
        TickData.objects.filter(
            instrument=instrument,
            timestamp__gte=start_dt,
            timestamp__lte=end_dt,
        )
        .order_by("timestamp")
        .values("timestamp", "bid", "ask", "mid")
    )
    buckets: dict[datetime, list[dict[str, Decimal | datetime]]] = {}
    for row in qs.iterator(chunk_size=batch_size):
        bucket = _bucket_start(row["timestamp"], bucket_seconds)
        buckets.setdefault(bucket, []).append(row)

    for bucket, rows in sorted(buckets.items(), key=lambda item: item[0]):
        if mode == "first":
            selected = rows[0]
            yield BacktestTickRow(
                timestamp=bucket,
                bid=Decimal(str(selected["bid"])),
                ask=Decimal(str(selected["ask"])),
                mid=Decimal(str(selected["mid"])),
            )
            continue

        if mode == "last":
            selected = rows[-1]
            yield BacktestTickRow(
                timestamp=bucket,
                bid=Decimal(str(selected["bid"])),
                ask=Decimal(str(selected["ask"])),
                mid=Decimal(str(selected["mid"])),
            )
            continue

        if mode == "average":
            count = Decimal(len(rows))
            yield BacktestTickRow(
                timestamp=bucket,
                bid=sum(Decimal(str(row["bid"])) for row in rows) / count,
                ask=sum(Decimal(str(row["ask"])) for row in rows) / count,
                mid=sum(Decimal(str(row["mid"])) for row in rows) / count,
            )
            continue

        yield BacktestTickRow(
            timestamp=bucket,
            bid=Decimal(str(median([Decimal(str(row["bid"])) for row in rows]))),
            ask=Decimal(str(median([Decimal(str(row["ask"])) for row in rows]))),
            mid=Decimal(str(median([Decimal(str(row["mid"])) for row in rows]))),
        )


def _bucket_start(timestamp: datetime, bucket_seconds: int) -> datetime:
    ts_utc = timestamp.astimezone(UTC)
    floored = int(ts_utc.timestamp()) // bucket_seconds * bucket_seconds
    return datetime.fromtimestamp(floored, tz=UTC)
