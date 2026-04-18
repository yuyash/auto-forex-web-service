"""Forex market session helpers used by the trading executor.

Forex markets run 24 hours a day from Sunday 21:00 UTC through Friday
21:00 UTC.  These helpers encapsulate the timing rules so that the executor
can:

* Detect the next upcoming close / open event, used to anticipate market
  close and switch a running task into IDLE mode shortly before it.
* Determine whether the market is currently open or closed.

The logic is intentionally tiny and dependency-free so it can be unit tested
without touching Django or Celery.  This mirrors and is kept in sync with
``apps.market.views.market.MarketStatusView`` which already implements the
same open/close rules for the public market-status REST endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Forex week: closed from Friday 21:00 UTC to Sunday 21:00 UTC.
_CLOSE_WEEKDAY = 4  # Friday
_CLOSE_HOUR_UTC = 21
_OPEN_WEEKDAY = 6  # Sunday
_OPEN_HOUR_UTC = 21


@dataclass(frozen=True, slots=True)
class MarketSchedule:
    """Snapshot of forex market state relative to ``now``."""

    is_open: bool
    next_close: datetime | None
    next_open: datetime | None

    @property
    def is_closed(self) -> bool:
        return not self.is_open


def is_forex_market_closed(now: datetime | None = None) -> bool:
    """Return True when the forex spot market is currently closed."""
    now = _ensure_utc(now)
    weekday = now.weekday()
    hour = now.hour
    return (
        (weekday == _CLOSE_WEEKDAY and hour >= _CLOSE_HOUR_UTC)
        or weekday == 5  # Saturday
        or (weekday == _OPEN_WEEKDAY and hour < _OPEN_HOUR_UTC)
    )


def next_market_close(now: datetime | None = None) -> datetime:
    """Return the datetime (UTC) of the upcoming Friday 21:00 close.

    If the market is currently closed this still returns the close that
    follows the next open — i.e. the next Friday 21:00 UTC.
    """
    now = _ensure_utc(now)
    # Jump to Friday 21:00 UTC this week, or next Friday if we're already past.
    days_until_friday = (_CLOSE_WEEKDAY - now.weekday()) % 7
    close = now.replace(hour=_CLOSE_HOUR_UTC, minute=0, second=0, microsecond=0) + timedelta(
        days=days_until_friday
    )
    if close <= now:
        close = close + timedelta(days=7)
    return close


def next_market_open(now: datetime | None = None) -> datetime:
    """Return the datetime (UTC) of the next Sunday 21:00 UTC open."""
    now = _ensure_utc(now)
    days_until_sunday = (_OPEN_WEEKDAY - now.weekday()) % 7
    open_at = now.replace(hour=_OPEN_HOUR_UTC, minute=0, second=0, microsecond=0) + timedelta(
        days=days_until_sunday
    )
    if open_at <= now:
        open_at = open_at + timedelta(days=7)
    return open_at


def current_schedule(now: datetime | None = None) -> MarketSchedule:
    """Return a combined snapshot of market state at ``now``."""
    now = _ensure_utc(now)
    closed = is_forex_market_closed(now)
    return MarketSchedule(
        is_open=not closed,
        next_close=None if closed else next_market_close(now),
        next_open=next_market_open(now) if closed else None,
    )


def should_enter_pre_close_idle(
    *,
    now: datetime,
    pre_close_minutes: int,
) -> bool:
    """True when we are within ``pre_close_minutes`` of the upcoming close.

    Only meaningful while the market is open.  Returns False when
    ``pre_close_minutes`` is 0 (feature disabled).
    """
    if pre_close_minutes <= 0:
        return False
    now = _ensure_utc(now)
    if is_forex_market_closed(now):
        return False
    close = next_market_close(now)
    return close - now <= timedelta(minutes=pre_close_minutes)


def should_resume_from_idle(
    *,
    now: datetime,
    idle_entered_at: datetime | None,
    resume_delay_minutes: int,
) -> bool:
    """True when we may resume trading after idling through a market close.

    This expects the market to already be open; callers should short-circuit
    otherwise.  The optional ``resume_delay_minutes`` ensures we wait a bit
    after the reopen to avoid trading into the thin first minutes of the
    session.
    """
    now = _ensure_utc(now)
    if is_forex_market_closed(now):
        return False
    if resume_delay_minutes <= 0 or idle_entered_at is None:
        return True

    idle_entered_at = _ensure_utc(idle_entered_at)
    # Use the later of (idle entry + delay) and (last market open + delay).
    last_open = _previous_market_open(now)
    delay = timedelta(minutes=resume_delay_minutes)
    earliest_resume = max(idle_entered_at + delay, last_open + delay)
    return now >= earliest_resume


def _previous_market_open(now: datetime) -> datetime:
    """The most recent Sunday 21:00 UTC open at or before ``now``."""
    candidate = now.replace(hour=_OPEN_HOUR_UTC, minute=0, second=0, microsecond=0)
    days_since_sunday = (candidate.weekday() - _OPEN_WEEKDAY) % 7
    candidate = candidate - timedelta(days=days_since_sunday)
    if candidate > now:
        candidate = candidate - timedelta(days=7)
    return candidate


def _ensure_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)
