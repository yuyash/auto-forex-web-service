from __future__ import annotations

from argparse import ArgumentParser
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

import boto3
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.market.models import TickData


@dataclass(frozen=True)
class _AthenaRow:
    ticker: str
    instrument: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    mid: Decimal


def _parse_date_or_datetime(value: str, *, is_end: bool) -> datetime:
    """Parse an ISO date or datetime to a timezone-aware UTC datetime.

    If `value` is a date (YYYY-MM-DD), it's interpreted as:
    - start: inclusive at 00:00:00Z
    - end: inclusive at 23:59:59.999999Z

    If `value` is a datetime, it's converted to UTC.
    """

    value_str = str(value).strip()

    # Date-only input
    if "T" not in value_str and len(value_str) == 10:
        parsed_date = date.fromisoformat(value_str)
        return datetime.combine(
            parsed_date,
            dt_time.max if is_end else dt_time.min,
            tzinfo=timezone.utc,
        )

    # Datetime input
    if value_str.endswith("Z"):
        value_str = value_str[:-1] + "+00:00"

    dt = datetime.fromisoformat(value_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc


def _athena_timestamp_literal(dt: datetime) -> str:
    """Format a UTC datetime for Athena TIMESTAMP literals."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _ticker_to_instrument(ticker: str) -> str:
    """Best-effort conversion from common ticker formats to OANDA instruments."""

    raw = str(ticker).strip()
    if not raw:
        return raw

    # Strip known prefixes like "C:".
    if ":" in raw:
        raw = raw.split(":", 1)[1]

    raw = raw.replace("/", "_")
    raw = raw.replace("-", "_")

    if "_" in raw:
        return raw

    # e.g. EURUSD -> EUR_USD
    if len(raw) == 6:
        return f"{raw[:3]}_{raw[3:]}"

    return raw


def _parse_athena_row(row: list[dict[str, Any]]) -> list[str]:
    # Athena returns rows as: {"Data": [{"VarCharValue": "..."}, ...]}
    # We normalize into a list of string values.
    values: list[str] = []
    for cell in row:
        cell_value = cell.get("VarCharValue")
        values.append("" if cell_value is None else str(cell_value))
    return values


def _coerce_decimal(value: str) -> Decimal:
    value_str = str(value).strip()
    if value_str == "":
        raise ValueError("empty decimal")
    return Decimal(value_str)


def _parse_timestamp(value: str) -> datetime:
    # Common Athena output is "YYYY-MM-DD HH:MM:SS.sss" (no timezone)
    v = str(value).strip()
    if not v:
        raise ValueError("empty timestamp")

    if v.endswith("Z"):
        v = v[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        # Handle "YYYY-MM-DD HH:MM:SS" by converting to ISO with T
        dt = datetime.fromisoformat(v.replace(" ", "T"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _parse_epoch_ns(value: str) -> datetime:
    """Parse an epoch nanoseconds value into a UTC datetime."""

    raw = str(value).strip()
    if not raw:
        raise ValueError("empty epoch ns")

    ns = int(raw)
    seconds, nanos = divmod(ns, 1_000_000_000)
    # Python datetime supports microsecond resolution.
    microseconds = nanos // 1_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=microseconds)


def _to_epoch_ns(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt_utc - epoch
    total_seconds = delta.days * 86_400 + delta.seconds
    return total_seconds * 1_000_000_000 + dt_utc.microsecond * 1_000


def _partition_where_for_date_range(*, start_dt: datetime, end_dt: datetime) -> str:
    """Build an Athena WHERE predicate for (year, month, day) partitions.

    Assumes the table is partitioned by columns named: year, month, day.
    (Commonly these partition columns are stored as strings/varchars in Athena.)
    The range is interpreted as [start_dt, end_dt] in UTC.
    """

    if end_dt < start_dt:
        raise ValueError("end_dt must be on/after start_dt")

    start_date = start_dt.astimezone(timezone.utc).date()
    last_inclusive_date = end_dt.astimezone(timezone.utc).date()

    if last_inclusive_date < start_date:
        raise ValueError("empty date range")

    parts: list[str] = []
    current = start_date
    while current <= last_inclusive_date:
        month = f"{current.month:02d}"
        day = f"{current.day:02d}"
        parts.append(
            "(" f"year = '{current.year}' " f"AND month = '{month}' " f"AND day = '{day}'" ")"
        )
        current += timedelta(days=1)

    return "(" + " OR ".join(parts) + ")"


def _s3_output_location_from_bucket(bucket: str) -> str:
    """Convert a bucket name (or s3:// URL) into an Athena OutputLocation.

    Accepts:
    - my-bucket
    - my-bucket/some/prefix
    - s3://my-bucket
    - s3://my-bucket/some/prefix

    We append a default prefix so Athena can write objects.
    """

    raw = str(bucket).strip()
    if not raw:
        raise ValueError("empty bucket")

    if raw.startswith("s3://"):
        raw = raw[len("s3://") :]

    raw = raw.lstrip("/")

    # Ensure there's at least a folder-like prefix.
    if raw.endswith("/"):
        raw = raw[:-1]

    return f"s3://{raw}/athena-results/"


def _iter_ticks_from_athena_results(
    result_pages: Iterable[dict[str, Any]],
    *,
    instrument_filter: str | None,
) -> Iterable[_AthenaRow]:
    header_skipped = False

    instrument_filter_str = (instrument_filter or "").strip() or None
    expected_instrument = (
        _ticker_to_instrument(instrument_filter_str) if instrument_filter_str else None
    )

    for page in result_pages:
        rows = page.get("ResultSet", {}).get("Rows", [])
        for raw_row in rows:
            data = raw_row.get("Data", [])
            values = _parse_athena_row(data)

            # Skip header row once.
            if not header_skipped:
                header_skipped = True
                continue

            # Expected columns (Athena): ticker, bid_price, ask_price, participant_timestamp
            if len(values) < 4:
                continue

            ticker = values[0]
            instrument = _ticker_to_instrument(ticker)

            if instrument_filter_str and expected_instrument:
                ticker_match = str(ticker).strip() == instrument_filter_str
                instrument_match = instrument == expected_instrument
                if not (ticker_match or instrument_match):
                    continue

            bid = _coerce_decimal(values[1])
            ask = _coerce_decimal(values[2])
            timestamp = _parse_epoch_ns(values[3])
            mid = TickData.calculate_mid(bid, ask)

            yield _AthenaRow(
                ticker=ticker,
                instrument=instrument,
                timestamp=timestamp,
                bid=bid,
                ask=ask,
                mid=mid,
            )


class Command(BaseCommand):
    help = "Load historical tick data from AWS Athena into TickData."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--start",
            required=True,
            help="Start date/datetime (YYYY-MM-DD or ISO8601 datetime).",
        )
        parser.add_argument(
            "--end",
            required=True,
            help="End date/datetime (YYYY-MM-DD or ISO8601 datetime). End is inclusive.",
        )
        parser.add_argument(
            "--database",
            required=True,
            help="Athena database name.",
        )
        parser.add_argument(
            "--table",
            required=True,
            help="Athena table name.",
        )
        parser.add_argument(
            "--profile",
            default=None,
            help="AWS profile name (optional).",
        )
        parser.add_argument(
            "--output-bucket",
            default=None,
            help=(
                "S3 bucket (or s3:// URL) to store Athena query results. "
                "If set, results are written under <bucket>/athena-results/."
            ),
        )
        parser.add_argument(
            "--instrument",
            default="C:USD-JPY",
            help="Instrument/ticker to load (default: C:USD-JPY).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        start_raw: str = options["start"]
        end_raw: str = options["end"]
        database: str = options["database"]
        table: str = options["table"]
        profile: str | None = options.get("profile")
        output_bucket: str | None = options.get("output_bucket")
        instrument_filter: str = str(options.get("instrument") or "C:USD-JPY")

        try:
            start_dt = _parse_date_or_datetime(start_raw, is_end=False)
            end_dt = _parse_date_or_datetime(end_raw, is_end=True)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise CommandError(f"Invalid --start/--end: {exc}") from exc

        if end_dt < start_dt:
            raise CommandError("--end must be on/after --start")

        instrument_filter_str = str(instrument_filter).strip().strip("\"'")
        if not instrument_filter_str:
            raise CommandError("--instrument must not be empty")

        quoted_ticker = f"'{instrument_filter_str.replace("'", "''")}'"

        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        athena = session.client("athena")

        total_created = 0

        upsert_kwargs: dict[str, Any] = {
            "update_conflicts": True,
            "update_fields": ["bid", "ask", "mid"],
            "unique_fields": ["instrument", "timestamp"],
        }

        def _flush(batch: list[TickData]) -> int:
            if not batch:
                return 0

            # Postgres raises CARDINALITY_VIOLATION if the same conflict key
            # appears multiple times in one INSERT ... ON CONFLICT statement.
            # This can happen if the upstream data contains duplicates, or if
            # multiple nanosecond timestamps collapse to the same microsecond.
            unique: dict[tuple[str, datetime], TickData] = {}
            for obj in batch:
                unique[(str(obj.instrument), obj.timestamp)] = obj

            unique_batch = list(unique.values())
            TickData.objects.bulk_create(unique_batch, **upsert_kwargs)
            return len(unique_batch)

        start_date = start_dt.astimezone(timezone.utc).date()
        end_date = end_dt.astimezone(timezone.utc).date()

        window_start = start_date
        while window_start <= end_date:
            window_end = min(window_start + timedelta(days=9), end_date)

            chunk_start = datetime.combine(window_start, dt_time.min, tzinfo=timezone.utc)
            chunk_end = datetime.combine(window_end, dt_time.max, tzinfo=timezone.utc)

            try:
                partition_filter_sql = _partition_where_for_date_range(
                    start_dt=chunk_start, end_dt=chunk_end
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                raise CommandError(f"Failed to build partition filter: {exc}") from exc

            query = (
                "SELECT\n"
                "    ticker,\n"
                "    bid_price,\n"
                "    ask_price,\n"
                "    participant_timestamp\n"
                f'FROM "{database}"."{table}"\n'
                f"WHERE {partition_filter_sql}\n"
                f"  AND ticker = {quoted_ticker}\n"
                "ORDER BY participant_timestamp ASC"
            )

            self.stdout.write(
                "Starting Athena query "
                f"for {database}.{table} instrument={instrument_filter_str} "
                f"from {chunk_start.isoformat()} to {chunk_end.isoformat()}"
            )

            try:
                start_kwargs: dict[str, Any] = {
                    "QueryString": query,
                    "QueryExecutionContext": {"Database": database},
                }

                if output_bucket:
                    start_kwargs["ResultConfiguration"] = {
                        "OutputLocation": _s3_output_location_from_bucket(output_bucket)
                    }

                response = athena.start_query_execution(**start_kwargs)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                raise CommandError(f"Failed to start Athena query: {exc}") from exc

            query_execution_id = response.get("QueryExecutionId")
            if not query_execution_id:
                raise CommandError("Athena did not return a QueryExecutionId")

            timeout_seconds = 600
            start_time = time.monotonic()
            state: str | None = None
            state_reason: str | None = None

            while True:
                if time.monotonic() - start_time > timeout_seconds:
                    raise CommandError(f"Timed out waiting for Athena query {query_execution_id}")

                status = athena.get_query_execution(QueryExecutionId=query_execution_id)
                execution = status.get("QueryExecution", {})
                status_block = execution.get("Status", {})
                state = status_block.get("State")
                state_reason = status_block.get("StateChangeReason")

                if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    break

                time.sleep(1.0)

            if state != "SUCCEEDED":
                reason = state_reason or "Unknown"
                raise CommandError(
                    f"Athena query {query_execution_id} did not succeed (state={state}): {reason}"
                )

            paginator = athena.get_paginator("get_query_results")
            pages = paginator.paginate(QueryExecutionId=query_execution_id)

            created_count = 0
            batch: list[TickData] = []
            batch_size = 1000

            with transaction.atomic():
                for tick in _iter_ticks_from_athena_results(
                    pages, instrument_filter=instrument_filter_str
                ):
                    batch.append(
                        TickData(
                            instrument=tick.instrument,
                            timestamp=tick.timestamp,
                            bid=tick.bid,
                            ask=tick.ask,
                            mid=tick.mid,
                        )
                    )

                    if len(batch) >= batch_size:
                        created_count += _flush(batch)
                        batch.clear()

                if batch:
                    created_count += _flush(batch)

            total_created += created_count
            self.stdout.write(
                self.style.SUCCESS(
                    f"Inserted {created_count} tick rows for "
                    f"{chunk_start.date()}..{chunk_end.date()}"
                )
            )

            window_start = window_end + timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Inserted {total_created} tick rows"))
