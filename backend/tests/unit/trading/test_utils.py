"""Unit tests for trading utility functions."""

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.utils import normalize_instance_key, parse_iso_datetime, pip_size_for_instrument


class TestPipSizeForInstrument:
    """Tests for pip_size_for_instrument function."""

    def test_jpy_pair_returns_0_01(self):
        """JPY pairs should return 0.01 pip size."""
        assert pip_size_for_instrument("USD_JPY") == Decimal("0.01")
        assert pip_size_for_instrument("EUR_JPY") == Decimal("0.01")
        assert pip_size_for_instrument("GBP_JPY") == Decimal("0.01")

    def test_non_jpy_pair_returns_0_0001(self):
        """Non-JPY pairs should return 0.0001 pip size."""
        assert pip_size_for_instrument("EUR_USD") == Decimal("0.0001")
        assert pip_size_for_instrument("GBP_USD") == Decimal("0.0001")
        assert pip_size_for_instrument("AUD_CAD") == Decimal("0.0001")

    def test_case_insensitive(self):
        """Function should handle case-insensitive instrument names."""
        assert pip_size_for_instrument("usd_jpy") == Decimal("0.01")
        assert pip_size_for_instrument("eur_usd") == Decimal("0.0001")
        assert pip_size_for_instrument("Eur_Usd") == Decimal("0.0001")

    def test_jpy_in_any_position(self):
        """JPY detection should work regardless of position in pair."""
        assert pip_size_for_instrument("JPY_USD") == Decimal("0.01")
        assert pip_size_for_instrument("USD_JPY") == Decimal("0.01")


class TestNormalizeInstanceKey:
    """Tests for normalize_instance_key function."""

    def test_none_returns_default(self):
        """None should return 'default'."""
        assert normalize_instance_key(None) == "default"

    def test_string_returns_same_string(self):
        """String values should be returned as-is."""
        assert normalize_instance_key("my-key") == "my-key"
        assert normalize_instance_key("task-123") == "task-123"

    def test_empty_string_returns_default(self):
        """Empty string should return 'default' (treated as falsy)."""
        assert normalize_instance_key("") == "default"

    def test_numeric_converted_to_string(self):
        """Numeric values should be converted to strings."""
        assert normalize_instance_key(123) == "123"  # type: ignore
        assert normalize_instance_key(45.67) == "45.67"  # type: ignore


class TestParseIsoDatetime:
    """Tests for parse_iso_datetime function."""

    def test_none_returns_none(self):
        """None input should return None."""
        assert parse_iso_datetime(None) is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_iso_datetime("") is None
        assert parse_iso_datetime("   ") is None

    def test_valid_iso_with_timezone(self):
        """Valid ISO datetime with timezone should parse correctly."""
        result = parse_iso_datetime("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo is not None

    def test_valid_iso_with_z_suffix(self):
        """ISO datetime with 'Z' suffix should be converted to UTC."""
        result = parse_iso_datetime("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo == UTC

    def test_valid_iso_without_timezone(self):
        """ISO datetime without timezone should be assumed UTC."""
        result = parse_iso_datetime("2024-01-15T10:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo == UTC

    def test_valid_iso_with_microseconds(self):
        """ISO datetime with microseconds should parse correctly."""
        result = parse_iso_datetime("2024-01-15T10:30:00.123456+00:00")
        assert result is not None
        assert result.microsecond == 123456

    def test_valid_iso_with_different_timezone(self):
        """ISO datetime with non-UTC timezone should preserve timezone."""
        result = parse_iso_datetime("2024-01-15T10:30:00-05:00")
        assert result is not None
        assert result.tzinfo is not None
        # Check that it's not UTC
        assert result.tzinfo != UTC

    def test_invalid_format_returns_none(self):
        """Invalid datetime format should return None."""
        assert parse_iso_datetime("not-a-date") is None
        assert parse_iso_datetime("2024-13-45") is None
        assert parse_iso_datetime("15/01/2024") is None

    def test_numeric_input_returns_none(self):
        """Numeric input should return None."""
        assert parse_iso_datetime(12345) is None

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed."""
        result = parse_iso_datetime("  2024-01-15T10:30:00Z  ")
        assert result is not None
        assert result.year == 2024

    def test_datetime_object_converted_to_string(self):
        """Datetime object should be converted to string and parsed."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = parse_iso_datetime(dt)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
