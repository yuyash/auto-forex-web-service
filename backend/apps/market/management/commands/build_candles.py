"""Build local OHLC candles from stored tick data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, Min
from django.utils import timezone

from apps.market.models import TickData
from apps.market.services.candles import (
    CANDLE_GRANULARITY_SECONDS,
    market_candle_service,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommandError(f"Invalid datetime: {value}") from exc
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


class Command(BaseCommand):
    """Backfill ``market_candles`` for one instrument and date range."""

    help = "Build market_candles rows from TickData or stored M1 candles."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--instrument", required=True, help="Instrument such as USD_JPY.")
        parser.add_argument(
            "--granularity",
            action="append",
            choices=sorted(CANDLE_GRANULARITY_SECONDS),
            default=None,
            help="Granularity to build. Repeat to build multiple granularities.",
        )
        parser.add_argument("--since", help="Inclusive start timestamp.")
        parser.add_argument("--until", help="Exclusive end timestamp.")
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args: Any, **options: Any) -> None:
        instrument = str(options["instrument"]).strip().upper()
        granularities = sorted(
            set(options["granularity"] or ["M1"]),
            key=lambda value: CANDLE_GRANULARITY_SECONDS[value],
        )
        since = _parse_datetime(options.get("since"))
        until = _parse_datetime(options.get("until"))

        if since is None or until is None:
            bounds = TickData.objects.filter(instrument=instrument).aggregate(
                min_ts=Min("timestamp"),
                max_ts=Max("timestamp"),
            )
            since = since or bounds["min_ts"]
            until = until or (
                bounds["max_ts"] + timedelta(microseconds=1) if bounds["max_ts"] else None
            )
        if since is None or until is None:
            raise CommandError(f"No TickData found for {instrument}.")
        if since >= until:
            raise CommandError("since must be earlier than until.")

        for granularity in granularities:
            stats = market_candle_service.backfill(
                instrument=instrument,
                granularity=granularity,
                since=since,
                until=until,
                batch_size=int(options["batch_size"]),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Built {stats.candles} {stats.instrument} {stats.granularity} candles."
                )
            )
