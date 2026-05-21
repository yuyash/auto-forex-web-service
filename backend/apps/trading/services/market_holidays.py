"""Major FX-market holiday calendar.

Provides a set of dates on which forex liquidity is severely reduced
because two or more of the major FX trading centres (US, UK, EU/Germany)
are observing a public holiday.  Examples include Christmas Day, Boxing
Day, New Year's Day and Good Friday.

Local-only holidays — such as US Memorial Day, German Reunification Day,
or UK Spring Bank Holiday — do not trigger a calendar entry because
liquidity is still available from the other two centres.

The calendar is consumed by :mod:`apps.trading.services.market_schedule`
through ``MarketSessionConfig.holiday_dates``.  Backtests opt-in via the
``BacktestTask.holidays_enabled`` flag and may extend or override the
list with ``BacktestTask.excluded_dates``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from functools import lru_cache
import re
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import holidays

from apps.trading.services.market_schedule import MarketClosedWindow

# Default major FX centres.  We keep the list intentionally small — the
# goal is to catch days where liquidity disappears across the board, not
# every regional bank holiday.
DEFAULT_FX_COUNTRIES: tuple[str, ...] = ("US", "GB", "DE")

# A date is treated as a major FX holiday when it is observed in at least
# this many of the configured countries.  With three countries and a
# threshold of two, single-country observances are ignored.
DEFAULT_HOLIDAY_THRESHOLD: int = 2
_MONTH_DAY_RE = re.compile(r"^(?P<month>\d{2})-(?P<day>\d{2})$")


@lru_cache(maxsize=64)
def _country_year_dates(country: str, year: int) -> frozenset[date]:
    """Return the holiday dates observed in ``country`` for ``year``.

    The result is cached to avoid rebuilding the (relatively expensive)
    :mod:`holidays` country dictionary on every call.
    """
    return frozenset(holidays.country_holidays(country, years=[year]).keys())


def major_fx_holidays(
    years: Iterable[int],
    *,
    countries: Iterable[str] = DEFAULT_FX_COUNTRIES,
    threshold: int = DEFAULT_HOLIDAY_THRESHOLD,
) -> frozenset[date]:
    """Return the union of dates that are major FX holidays.

    A date qualifies when it is a public holiday in at least ``threshold``
    of the supplied ``countries``.
    """
    country_list = tuple(c.upper() for c in countries)
    if not country_list:
        return frozenset()

    effective_threshold = max(1, min(threshold, len(country_list)))

    counts: dict[date, int] = {}
    for year in {int(y) for y in years}:
        for country in country_list:
            for d in _country_year_dates(country, year):
                counts[d] = counts.get(d, 0) + 1

    return frozenset(d for d, n in counts.items() if n >= effective_threshold)


def major_fx_holidays_between(
    start: date,
    end: date,
    *,
    countries: Iterable[str] = DEFAULT_FX_COUNTRIES,
    threshold: int = DEFAULT_HOLIDAY_THRESHOLD,
) -> frozenset[date]:
    """Return major FX holidays in the inclusive ``start``–``end`` window."""
    if end < start:
        return frozenset()

    years = range(start.year, end.year + 1)
    candidates = major_fx_holidays(years, countries=countries, threshold=threshold)
    return frozenset(d for d in candidates if start <= d <= end)


def parse_excluded_dates(
    values: Iterable[object] | None,
    *,
    start: date | None = None,
    end: date | None = None,
) -> frozenset[date]:
    """Parse custom market-closed dates into a concrete date set.

    Supported string formats:

    * ``YYYY-MM-DD`` for one specific UTC calendar date.
    * ``MM-DD`` for a recurring annual date, expanded across the inclusive
      ``start``–``end`` window when both bounds are supplied.

    Invalid or empty entries are silently skipped — validation of the
    user-supplied list happens in the serializer; this helper is meant to
    be tolerant when reading values back from existing tasks.
    """
    if not values:
        return frozenset()

    out: set[date] = set()
    for raw in values:
        if isinstance(raw, dict):
            continue
        if isinstance(raw, date):
            out.add(raw)
            continue
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            out.add(date.fromisoformat(text))
            continue
        except ValueError:
            pass

        month_day = _parse_month_day(text)
        if month_day is None or start is None or end is None or end < start:
            continue
        month, day = month_day
        for year in range(start.year, end.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if start <= candidate <= end:
                out.add(candidate)
    return frozenset(out)


def parse_excluded_windows(values: Iterable[object] | None) -> tuple[MarketClosedWindow, ...]:
    """Parse custom market-closed datetime windows.

    Newer backtest tasks store additional market closures as dictionaries:

    ``{"start": "...", "end": "...", "timezone": "America/New_York"}``

    ``start`` and ``end`` may be offset-aware ISO-8601 datetimes.  If a
    datetime has no offset, it is interpreted in the supplied IANA
    timezone.  Invalid entries are skipped here because serializer
    validation is responsible for rejecting malformed user input.
    """
    if not values:
        return ()

    windows: list[MarketClosedWindow] = []
    for raw in values:
        if not isinstance(raw, Mapping):
            continue
        raw_mapping = cast("Mapping[str, object]", raw)
        timezone = str(raw_mapping.get("timezone") or "UTC").strip() or "UTC"
        try:
            start = parse_closed_window_datetime(
                raw_mapping.get("start"),
                timezone=timezone,
            )
            end = parse_closed_window_datetime(
                raw_mapping.get("end"),
                timezone=timezone,
            )
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            continue
        if start >= end:
            continue
        windows.append(MarketClosedWindow(start=start, end=end))

    return tuple(sorted(windows, key=lambda window: window.start))


def parse_closed_window_datetime(value: object, *, timezone: str) -> datetime:
    """Parse a datetime value and return it normalized to UTC."""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("datetime is required")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    else:
        # Validate the configured timezone even when the timestamp carries
        # an offset; the timezone is kept for editing/display in the UI.
        ZoneInfo(timezone)
    return parsed.astimezone(UTC)


def serialize_closed_window_datetime(value: datetime) -> str:
    """Serialize a UTC datetime for JSON API responses."""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_month_day(value: str) -> tuple[int, int] | None:
    match = _MONTH_DAY_RE.fullmatch(value)
    if match is None:
        return None
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        date(2000, month, day)
    except ValueError:
        return None
    return month, day


def resolve_holiday_dates(
    *,
    enabled: bool,
    start: date | None,
    end: date | None,
    excluded_dates: Iterable[object] | None,
    countries: Iterable[str] = DEFAULT_FX_COUNTRIES,
    threshold: int = DEFAULT_HOLIDAY_THRESHOLD,
) -> frozenset[date]:
    """Compose the final holiday-date set for a task.

    The major FX calendar is included only when ``enabled`` is True; the
    user-supplied ``excluded_dates`` are always merged in so that ad-hoc
    exclusions work even when the auto-calendar is off.
    """
    custom = parse_excluded_dates(excluded_dates, start=start, end=end)
    if not enabled:
        return custom
    if start is None or end is None:
        major = frozenset()
    else:
        major = major_fx_holidays_between(
            start,
            end,
            countries=countries,
            threshold=threshold,
        )
    return frozenset(major | custom)
