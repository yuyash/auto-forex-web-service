"""Unit tests for MarketSessionConfig.holiday_dates handling."""

from __future__ import annotations

from datetime import date, datetime, timezone

from apps.trading.services.market_schedule import (
    MarketSessionConfig,
    current_schedule,
    is_forex_market_closed,
    should_enter_pre_close_idle,
    should_resume_from_idle,
)


class TestHolidayClosure:
    """Tests for holiday_dates affecting is_forex_market_closed."""

    def test_holiday_on_weekday_closes_market(self) -> None:
        # 2024-12-25 is a Wednesday.
        cfg = MarketSessionConfig(
            enabled=True,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        wednesday_noon = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        assert is_forex_market_closed(wednesday_noon, config=cfg) is True

    def test_holiday_closure_works_when_weekly_close_disabled(self) -> None:
        cfg = MarketSessionConfig(
            enabled=False,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        wednesday_noon = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        assert is_forex_market_closed(wednesday_noon, config=cfg) is True

    def test_non_holiday_weekday_remains_open(self) -> None:
        cfg = MarketSessionConfig(
            enabled=True,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        thursday_noon = datetime(2024, 12, 26, 12, 0, tzinfo=timezone.utc)

        # Thursday with no holiday entry is open during the trading week.
        assert is_forex_market_closed(thursday_noon, config=cfg) is False

    def test_holiday_at_midnight_utc_is_closed(self) -> None:
        cfg = MarketSessionConfig(
            enabled=True,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        midnight = datetime(2024, 12, 25, 0, 0, tzinfo=timezone.utc)
        last_second = datetime(2024, 12, 25, 23, 59, 59, tzinfo=timezone.utc)

        assert is_forex_market_closed(midnight, config=cfg) is True
        assert is_forex_market_closed(last_second, config=cfg) is True

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        cfg = MarketSessionConfig(
            enabled=True,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        naive_noon = datetime(2024, 12, 25, 12, 0)

        assert is_forex_market_closed(naive_noon, config=cfg) is True

    def test_holiday_dates_default_is_empty(self) -> None:
        cfg = MarketSessionConfig()

        assert cfg.holiday_dates == frozenset()
        assert cfg.has_holiday_calendar is False


class TestHolidayCurrentSchedule:
    """Tests for current_schedule respecting holiday_dates."""

    def test_holiday_marks_schedule_as_closed(self) -> None:
        cfg = MarketSessionConfig(
            enabled=True,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        wednesday_noon = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        snap = current_schedule(wednesday_noon, config=cfg)

        assert snap.is_open is False
        assert snap.is_closed is True

    def test_holiday_only_mode_reports_open_on_other_days(self) -> None:
        cfg = MarketSessionConfig(
            enabled=False,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        thursday_noon = datetime(2024, 12, 26, 12, 0, tzinfo=timezone.utc)

        snap = current_schedule(thursday_noon, config=cfg)

        assert snap.is_open is True
        assert snap.next_close is None
        assert snap.next_open is None


class TestHolidayPreCloseAndResume:
    """Tests for should_enter_pre_close_idle / should_resume_from_idle."""

    def test_pre_close_returns_false_when_weekly_disabled(self) -> None:
        cfg = MarketSessionConfig(
            enabled=False,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        wednesday = datetime(2024, 12, 24, 20, 30, tzinfo=timezone.utc)

        # Without a weekly close there is no anchor for a pre-close window.
        assert should_enter_pre_close_idle(now=wednesday, pre_close_minutes=30, config=cfg) is False

    def test_resume_blocked_during_holiday(self) -> None:
        cfg = MarketSessionConfig(
            enabled=False,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        wednesday_noon = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        assert (
            should_resume_from_idle(
                now=wednesday_noon,
                idle_entered_at=None,
                resume_delay_minutes=0,
                config=cfg,
            )
            is False
        )

    def test_resume_allowed_after_holiday(self) -> None:
        cfg = MarketSessionConfig(
            enabled=False,
            holiday_dates=frozenset({date(2024, 12, 25)}),
        )
        next_day_noon = datetime(2024, 12, 26, 12, 0, tzinfo=timezone.utc)

        assert (
            should_resume_from_idle(
                now=next_day_noon,
                idle_entered_at=None,
                resume_delay_minutes=0,
                config=cfg,
            )
            is True
        )
