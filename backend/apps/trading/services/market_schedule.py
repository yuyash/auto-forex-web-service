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

A :class:`MarketSessionConfig` can be supplied to override the default
forex schedule — for example a backtest can specify a different close /
open weekday-hour pair, or disable the weekly close entirely.  When no
config is passed the default forex schedule is used, which matches the
historical hard-coded behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

# Forex week: closed from Friday 21:00 UTC to Sunday 21:00 UTC.
_CLOSE_WEEKDAY = 4  # Friday
_CLOSE_HOUR_UTC = 21
_OPEN_WEEKDAY = 6  # Sunday
_OPEN_HOUR_UTC = 21


@dataclass(frozen=True, slots=True)
class MarketClosedWindow:
    """Explicit market-closed datetime interval in UTC.

    ``start`` is inclusive and ``end`` is exclusive.  Callers should
    normalize both values to UTC before constructing the window.
    """

    start: datetime
    end: datetime

    def contains(self, value: datetime) -> bool:
        """Return True when ``value`` falls inside the closed interval."""
        now = _ensure_utc(value)
        return self.start <= now < self.end


@dataclass(frozen=True, slots=True)
class MarketSessionConfig:
    """Weekly market session definition.

    ``enabled=False`` means "there is no weekly close" — the market is
    always considered open, so none of the schedule helpers will report
    a closed window.  ``close_weekday`` and ``open_weekday`` follow
    ``datetime.weekday()`` semantics (0 = Monday … 6 = Sunday) and the
    hours are integers in the 0–23 UTC range.

    ``holiday_dates`` is an optional set of UTC calendar dates on which
    the market should be treated as closed for the entire 24-hour
    window.  ``holiday_windows`` is an optional set of exact UTC
    datetime intervals for ad-hoc closures such as early Christmas
    closes.  Both are honoured even when ``enabled`` is False so that
    callers can opt out of the weekly close while still suppressing
    trading on illiquid major-market holidays such as Christmas.
    """

    enabled: bool = True
    close_weekday: int = _CLOSE_WEEKDAY
    close_hour_utc: int = _CLOSE_HOUR_UTC
    open_weekday: int = _OPEN_WEEKDAY
    open_hour_utc: int = _OPEN_HOUR_UTC
    holiday_dates: frozenset[date] = field(default_factory=frozenset)
    holiday_windows: tuple[MarketClosedWindow, ...] = field(default_factory=tuple)

    @property
    def has_weekly_close(self) -> bool:
        """Whether the weekly Friday→Sunday close is active."""
        return self.enabled

    @property
    def has_holiday_calendar(self) -> bool:
        """Whether at least one explicit holiday date/window is configured."""
        return bool(self.holiday_dates or self.holiday_windows)


DEFAULT_SESSION_CONFIG = MarketSessionConfig()


@dataclass(frozen=True, slots=True)
class MarketSchedule:
    """Snapshot of forex market state relative to ``now``."""

    is_open: bool
    next_close: datetime | None
    next_open: datetime | None

    @property
    def is_closed(self) -> bool:
        return not self.is_open


def is_forex_market_closed(
    now: datetime | None = None,
    *,
    config: MarketSessionConfig | None = None,
) -> bool:
    """Return True when the forex spot market is currently closed.

    With the default config this returns True for Friday-21:00-UTC
    through Sunday-21:00-UTC.  When ``config.enabled`` is False the
    weekly close is ignored but configured ``holiday_dates`` and
    ``holiday_windows`` still cause the market to be reported as closed.
    """
    cfg = config or DEFAULT_SESSION_CONFIG
    now = _ensure_utc(now)
    if cfg.holiday_windows and any(window.contains(now) for window in cfg.holiday_windows):
        return True
    if cfg.holiday_dates and now.date() in cfg.holiday_dates:
        return True
    if not cfg.enabled:
        return False
    close_dt = _previous_close(now, cfg)
    open_dt = _next_open_on_or_after(close_dt, cfg)
    # Closed window is [close_dt, open_dt).  If now falls inside, the
    # market is closed; otherwise we are between open and the next
    # upcoming close, which is "open".
    return close_dt <= now < open_dt


def next_market_close(
    now: datetime | None = None,
    *,
    config: MarketSessionConfig | None = None,
) -> datetime:
    """Return the datetime (UTC) of the upcoming market close.

    When the market is currently closed this returns the close that
    follows the next open.  Raises ``ValueError`` if the configured
    schedule has ``enabled=False`` (no close exists).
    """
    cfg = config or DEFAULT_SESSION_CONFIG
    if not cfg.enabled:
        raise ValueError("next_market_close requires an enabled schedule")
    now = _ensure_utc(now)
    return _next_weekly_occurrence(now, weekday=cfg.close_weekday, hour=cfg.close_hour_utc)


def next_market_open(
    now: datetime | None = None,
    *,
    config: MarketSessionConfig | None = None,
) -> datetime:
    """Return the datetime (UTC) of the next market open."""
    cfg = config or DEFAULT_SESSION_CONFIG
    if not cfg.enabled:
        raise ValueError("next_market_open requires an enabled schedule")
    now = _ensure_utc(now)
    return _next_weekly_occurrence(now, weekday=cfg.open_weekday, hour=cfg.open_hour_utc)


def current_schedule(
    now: datetime | None = None,
    *,
    config: MarketSessionConfig | None = None,
) -> MarketSchedule:
    """Return a combined snapshot of market state at ``now``."""
    cfg = config or DEFAULT_SESSION_CONFIG
    now = _ensure_utc(now)
    closed = is_forex_market_closed(now, config=cfg)
    if not cfg.enabled:
        # Weekly close disabled — no next_close/next_open to surface.
        # Holidays may still be flipping ``closed`` for the current day.
        return MarketSchedule(is_open=not closed, next_close=None, next_open=None)
    return MarketSchedule(
        is_open=not closed,
        next_close=None if closed else next_market_close(now, config=cfg),
        next_open=next_market_open(now, config=cfg) if closed else None,
    )


def should_enter_pre_close_idle(
    *,
    now: datetime,
    pre_close_minutes: int,
    config: MarketSessionConfig | None = None,
) -> bool:
    """True when we are within ``pre_close_minutes`` of the upcoming close.

    Only meaningful while the market is open.  Returns False when
    ``pre_close_minutes`` is 0 (feature disabled) or when the configured
    schedule has ``enabled=False`` (no upcoming weekly close to anchor
    the pre-close window on).
    """
    cfg = config or DEFAULT_SESSION_CONFIG
    if not cfg.enabled or pre_close_minutes <= 0:
        return False
    now = _ensure_utc(now)
    if is_forex_market_closed(now, config=cfg):
        return False
    close = next_market_close(now, config=cfg)
    return close - now <= timedelta(minutes=pre_close_minutes)


def should_resume_from_idle(
    *,
    now: datetime,
    idle_entered_at: datetime | None,
    resume_delay_minutes: int,
    config: MarketSessionConfig | None = None,
) -> bool:
    """True when we may resume trading after idling through a market close.

    This expects the market to already be open; callers should short-circuit
    otherwise.  The optional ``resume_delay_minutes`` ensures we wait a bit
    after the reopen to avoid trading into the thin first minutes of the
    session.  With ``config.enabled=False`` we always return True (there is
    no close to wait past).
    """
    cfg = config or DEFAULT_SESSION_CONFIG
    now = _ensure_utc(now)
    if is_forex_market_closed(now, config=cfg):
        return False
    if not cfg.enabled:
        # No weekly close — only holiday-based idle is possible, and the
        # day-by-day flip is handled by ``is_forex_market_closed`` above.
        return True
    if resume_delay_minutes <= 0 or idle_entered_at is None:
        return True

    idle_entered_at = _ensure_utc(idle_entered_at)
    # Use the later of (idle entry + delay) and (last market open + delay).
    last_open = _previous_open(now, cfg)
    delay = timedelta(minutes=resume_delay_minutes)
    earliest_resume = max(idle_entered_at + delay, last_open + delay)
    return now >= earliest_resume


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_weekly_occurrence(now: datetime, *, weekday: int, hour: int) -> datetime:
    """Return the next ``datetime`` strictly after ``now`` matching weekday/hour."""
    base = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - now.weekday()) % 7
    candidate = base + timedelta(days=days_ahead)
    if candidate <= now:
        candidate = candidate + timedelta(days=7)
    return candidate


def _previous_weekly_occurrence(now: datetime, *, weekday: int, hour: int) -> datetime:
    """Return the most recent ``datetime`` at or before ``now`` matching weekday/hour."""
    base = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_back = (now.weekday() - weekday) % 7
    candidate = base - timedelta(days=days_back)
    if candidate > now:
        candidate = candidate - timedelta(days=7)
    return candidate


def _previous_close(now: datetime, cfg: MarketSessionConfig) -> datetime:
    return _previous_weekly_occurrence(now, weekday=cfg.close_weekday, hour=cfg.close_hour_utc)


def _previous_open(now: datetime, cfg: MarketSessionConfig) -> datetime:
    return _previous_weekly_occurrence(now, weekday=cfg.open_weekday, hour=cfg.open_hour_utc)


def _next_open_on_or_after(dt: datetime, cfg: MarketSessionConfig) -> datetime:
    """Return the first open event at or after ``dt``."""
    candidate = dt.replace(hour=cfg.open_hour_utc, minute=0, second=0, microsecond=0)
    days_ahead = (cfg.open_weekday - dt.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate < dt:
        candidate = candidate + timedelta(days=7)
    return candidate


def _ensure_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)
