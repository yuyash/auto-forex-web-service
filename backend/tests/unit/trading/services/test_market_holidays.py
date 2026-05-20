"""Unit tests for the major-FX holiday calendar."""

from __future__ import annotations

from datetime import date

import pytest

from apps.trading.services.market_holidays import (
    DEFAULT_FX_COUNTRIES,
    DEFAULT_HOLIDAY_THRESHOLD,
    major_fx_holidays,
    major_fx_holidays_between,
    parse_excluded_dates,
    resolve_holiday_dates,
)


class TestMajorFxHolidays:
    """Tests for major_fx_holidays / major_fx_holidays_between."""

    def test_christmas_is_recognized(self) -> None:
        result = major_fx_holidays([2024])

        assert date(2024, 12, 25) in result

    def test_new_year_day_is_recognized(self) -> None:
        result = major_fx_holidays([2024, 2025])

        assert date(2024, 1, 1) in result
        assert date(2025, 1, 1) in result

    def test_good_friday_is_recognized(self) -> None:
        # 2024-03-29 is Good Friday and is observed in GB and DE.
        result = major_fx_holidays([2024])

        assert date(2024, 3, 29) in result

    def test_us_only_holiday_is_excluded(self) -> None:
        # Memorial Day 2024 is observed only in the US.
        result = major_fx_holidays([2024])

        assert date(2024, 5, 27) in result or date(2024, 5, 27) not in result
        # ↑ Spring Bank Holiday (UK) also falls on 2024-05-27, so be specific:
        # use July 4 which is unambiguously US-only.
        assert date(2024, 7, 4) not in result
        # Juneteenth is also US-only.
        assert date(2024, 6, 19) not in result

    def test_german_only_holiday_is_excluded(self) -> None:
        # Tag der Deutschen Einheit (Oct 3) is only DE.
        result = major_fx_holidays([2024])

        assert date(2024, 10, 3) not in result

    def test_threshold_one_includes_local_holidays(self) -> None:
        result = major_fx_holidays([2024], threshold=1)

        assert date(2024, 7, 4) in result
        assert date(2024, 10, 3) in result

    def test_between_filters_by_window(self) -> None:
        result = major_fx_holidays_between(
            date(2024, 12, 1),
            date(2024, 12, 31),
        )

        assert date(2024, 12, 25) in result
        assert date(2024, 1, 1) not in result

    def test_between_handles_inverted_window(self) -> None:
        result = major_fx_holidays_between(date(2025, 1, 1), date(2024, 12, 1))

        assert result == frozenset()

    def test_default_constants_are_consistent(self) -> None:
        # Defensive: the implementation assumes 3 countries with threshold 2.
        assert DEFAULT_HOLIDAY_THRESHOLD <= len(DEFAULT_FX_COUNTRIES)


class TestParseExcludedDates:
    """Tests for parse_excluded_dates."""

    def test_parses_iso_strings(self) -> None:
        result = parse_excluded_dates(["2024-12-25", "2025-01-01"])

        assert result == frozenset({date(2024, 12, 25), date(2025, 1, 1)})

    def test_accepts_date_objects(self) -> None:
        result = parse_excluded_dates([date(2024, 12, 25)])

        assert result == frozenset({date(2024, 12, 25)})

    def test_skips_blank_and_none(self) -> None:
        result = parse_excluded_dates(["", None, "2024-12-25"])

        assert result == frozenset({date(2024, 12, 25)})

    def test_skips_invalid_strings(self) -> None:
        result = parse_excluded_dates(["not-a-date", "2024-12-25"])

        assert result == frozenset({date(2024, 12, 25)})

    def test_empty_input_returns_empty(self) -> None:
        assert parse_excluded_dates(None) == frozenset()
        assert parse_excluded_dates([]) == frozenset()

    def test_expands_month_day_rules_across_window(self) -> None:
        result = parse_excluded_dates(
            ["12-25"],
            start=date(2024, 12, 1),
            end=date(2025, 12, 31),
        )

        assert result == frozenset({date(2024, 12, 25), date(2025, 12, 25)})

    def test_skips_month_day_rules_without_window(self) -> None:
        assert parse_excluded_dates(["12-25"]) == frozenset()


class TestResolveHolidayDates:
    """Tests for resolve_holiday_dates."""

    def test_disabled_with_no_excludes_returns_empty(self) -> None:
        result = resolve_holiday_dates(
            enabled=False,
            start=date(2024, 12, 1),
            end=date(2024, 12, 31),
            excluded_dates=None,
        )

        assert result == frozenset()

    def test_disabled_returns_only_user_excludes(self) -> None:
        result = resolve_holiday_dates(
            enabled=False,
            start=date(2024, 12, 1),
            end=date(2024, 12, 31),
            excluded_dates=["2024-12-31"],
        )

        assert result == frozenset({date(2024, 12, 31)})

    def test_enabled_returns_calendar_in_window(self) -> None:
        result = resolve_holiday_dates(
            enabled=True,
            start=date(2024, 12, 20),
            end=date(2024, 12, 31),
            excluded_dates=None,
        )

        assert date(2024, 12, 25) in result
        assert date(2024, 12, 26) in result  # Boxing Day GB+DE

    def test_enabled_merges_user_excludes(self) -> None:
        result = resolve_holiday_dates(
            enabled=True,
            start=date(2024, 12, 20),
            end=date(2024, 12, 31),
            excluded_dates=["2024-12-31"],
        )

        assert date(2024, 12, 25) in result
        assert date(2024, 12, 31) in result

    def test_enabled_with_no_window_falls_back_to_user_dates(self) -> None:
        result = resolve_holiday_dates(
            enabled=True,
            start=None,
            end=None,
            excluded_dates=["2024-12-25"],
        )

        assert result == frozenset({date(2024, 12, 25)})

    def test_resolve_expands_month_day_user_excludes(self) -> None:
        result = resolve_holiday_dates(
            enabled=False,
            start=date(2024, 12, 1),
            end=date(2025, 1, 31),
            excluded_dates=["12-25", "01-01"],
        )

        assert result == frozenset({date(2024, 12, 25), date(2025, 1, 1)})


@pytest.mark.parametrize(
    "year,expected",
    [
        (2024, date(2024, 12, 25)),
        (2025, date(2025, 12, 25)),
        (2026, date(2026, 12, 25)),
    ],
)
def test_christmas_is_in_calendar_for_multiple_years(year: int, expected: date) -> None:
    assert expected in major_fx_holidays([year])
