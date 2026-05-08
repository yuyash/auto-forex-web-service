"""OANDA candle fetch and parsing services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from logging import Logger, getLogger
from typing import Any

from apps.market.services.oanda_retry import OandaApiRequestExecutor
from apps.market.services.oanda_types import OandaAPIError

logger: Logger = getLogger(name=__name__)

OANDA_GRANULARITY_SECONDS: dict[str, int] = {
    "S5": 5,
    "S10": 10,
    "S15": 15,
    "S30": 30,
    "M1": 60,
    "M2": 120,
    "M4": 240,
    "M5": 300,
    "M10": 600,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D": 86400,
    "W": 604800,
    "M": 2592000,
}


class OandaCandleFetchError(Exception):
    """Raised when OANDA candle API returns a non-success status."""

    def __init__(self, status_code: int, body: Any = None):
        super().__init__(f"OANDA candles request failed (status={status_code})")
        self.status_code = status_code
        self.body = body


class OandaCandleParser:
    """Parse raw OANDA candle resources into API records."""

    def parse_many(self, raw_candles: list[Any]) -> list[dict[str, Any]]:
        """Convert raw v20 Candlestick objects into JSON-serialisable dicts."""
        result: list[dict[str, Any]] = []
        for candle in raw_candles:
            if not candle.complete:
                continue
            mid = candle.mid
            if not mid or not all([mid.o, mid.h, mid.l, mid.c]):
                continue
            time_obj = self.parse_time(candle)
            if time_obj is None:
                continue
            result.append(
                {
                    "time": int(time_obj.timestamp()),
                    "open": float(mid.o),
                    "high": float(mid.h),
                    "low": float(mid.l),
                    "close": float(mid.c),
                    "volume": int(candle.volume),
                }
            )
        return result

    def parse_time(self, raw_candle: Any) -> datetime | None:
        """Parse a candle timestamp into a datetime when possible."""
        raw_time = getattr(raw_candle, "time", None)
        if not isinstance(raw_time, str):
            return None
        try:
            return datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except ValueError:
            return None


class OandaCandleGateway:
    """Fetch raw candle batches from OANDA with shared retry semantics."""

    def __init__(self, *, request_executor: OandaApiRequestExecutor | None = None) -> None:
        self.request_executor = request_executor or OandaApiRequestExecutor()

    def fetch(self, api_context: Any, instrument: str, **params: Any) -> list[Any]:
        """Run one OANDA candle request."""
        try:
            response = self.request_executor.request(
                api_context.instrument.candles,
                label="Fetch OANDA candles",
                failure_message="Failed to fetch OANDA candles",
                instrument=instrument,
                **params,
            )
        except OandaAPIError as exc:
            detail = " ".join(
                part for part in [str(exc), getattr(exc, "internal_detail", "")] if part
            )
            match = re.search(
                r"\b(?P<status>400|401|403|404|405|409|422|429|500|502|503|504)\b",
                detail,
            )
            status_code = int(match.group("status")) if match else 502
            raise OandaCandleFetchError(status_code=status_code, body=detail) from exc
        return response.body.get("candles", []) if response.body else []


class OandaCandleHistoryService:
    """Fetch OANDA candles for count, cursor, and date-range requests."""

    def __init__(
        self,
        *,
        gateway: OandaCandleGateway | None = None,
        parser: OandaCandleParser | None = None,
        granularity_seconds: dict[str, int] | None = None,
    ) -> None:
        self.gateway = gateway or OandaCandleGateway()
        self.parser = parser or OandaCandleParser()
        self.granularity_seconds = granularity_seconds or OANDA_GRANULARITY_SECONDS

    def fetch_range(
        self,
        api_context: Any,
        instrument: str,
        granularity: str,
        from_time: str,
        to_time: str,
        base: dict[str, Any],
    ) -> list[Any]:
        """Fetch candles for a from/to range, paginating if needed."""
        try:
            from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            logger.error("Failed to parse time range: %s", exc)
            return []

        seconds = self.seconds_for(granularity)
        estimated = int((to_dt - from_dt).total_seconds() / seconds)
        if estimated > 5000:
            return self.fetch_paginated(api_context, instrument, granularity, from_dt, to_dt)
        return self.gateway.fetch(
            api_context,
            instrument,
            fromTime=from_time,
            toTime=to_time,
            **base,
        )

    def fetch_paginated(
        self,
        api_context: Any,
        instrument: str,
        granularity: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[Any]:
        """Fetch candles in batches when the range exceeds 5000."""
        all_candles: list[Any] = []
        current_from = from_dt
        seconds = self.seconds_for(granularity)

        while current_from < to_dt:
            current_to = datetime.fromtimestamp(
                min(current_from.timestamp() + 5000 * seconds, to_dt.timestamp()),
                tz=UTC,
            )
            batch = self.gateway.fetch(
                api_context,
                instrument,
                granularity=granularity,
                fromTime=current_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                toTime=current_to.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            )
            if not batch:
                break
            all_candles.extend(batch)

            last_dt = self.parser.parse_time(batch[-1])
            if last_dt is None:
                break
            current_from = datetime.fromtimestamp(last_dt.timestamp() + seconds, tz=UTC)

        logger.info("Pagination complete: fetched %d total candles", len(all_candles))
        return all_candles

    def fetch_count_paginated(
        self,
        api_context: Any,
        instrument: str,
        granularity: str,
        total_count: int,
        *,
        direction: str,
        cursor_time: str | None = None,
    ) -> list[Any]:
        """Fetch candles in batches when count-based requests exceed OANDA's 5000 cap."""
        max_batch_size = 5000
        remaining = total_count
        seconds = self.seconds_for(granularity)
        all_candles: list[Any] = []
        next_cursor = cursor_time

        while remaining > 0:
            batch_size = min(remaining, max_batch_size)
            params: dict[str, Any] = {"granularity": granularity, "count": batch_size}
            if direction == "forward":
                if next_cursor:
                    params["fromTime"] = next_cursor
            elif next_cursor:
                params["toTime"] = next_cursor

            batch = self.gateway.fetch(api_context, instrument, **params)
            if not batch:
                break

            if direction == "forward":
                all_candles.extend(batch)
                last_dt = self.parser.parse_time(batch[-1])
                if last_dt is None:
                    break
                next_cursor = datetime.fromtimestamp(
                    last_dt.timestamp() + seconds,
                    tz=UTC,
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                all_candles = [*batch, *all_candles]
                first_dt = self.parser.parse_time(batch[0])
                if first_dt is None:
                    break
                next_cursor = datetime.fromtimestamp(
                    first_dt.timestamp() - 1,
                    tz=UTC,
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            remaining -= len(batch)
            if len(batch) < batch_size:
                break

        return all_candles

    def seconds_for(self, granularity: str) -> int:
        """Return granularity seconds with H1 fallback."""
        return self.granularity_seconds.get(granularity, 3600)
