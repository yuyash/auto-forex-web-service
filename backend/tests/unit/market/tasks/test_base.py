"""Unit tests for market tasks base utilities."""

from datetime import UTC, datetime

from apps.market.tasks.base import (
    backtest_channel_for_request,
    isoformat,
    lock_value,
    parse_iso_datetime,
)


class TestBaseUtilities:
    """Test base utility functions."""

    def test_isoformat(self) -> None:
        """Test datetime to ISO format conversion."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        result = isoformat(dt)

        assert result == "2024-01-15T10:30:45Z"
        assert result.endswith("Z")

    def test_isoformat_naive_datetime(self) -> None:
        """Test isoformat with naive datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = isoformat(dt)

        assert result.endswith("Z")
        assert "2024-01-15" in result

    def test_parse_iso_datetime(self) -> None:
        """Test parsing ISO format datetime."""
        iso_str = "2024-01-15T10:30:45.000000Z"
        result = parse_iso_datetime(iso_str)

        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo is not None

    def test_parse_iso_datetime_with_offset(self) -> None:
        """Test parsing ISO datetime with timezone offset."""
        iso_str = "2024-01-15T10:30:45+00:00"
        result = parse_iso_datetime(iso_str)

        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_backtest_channel_for_request(self) -> None:
        """Test backtest channel name generation."""
        request_id = "test-request-123"
        channel = backtest_channel_for_request(request_id)

        assert "test-request-123" in channel
        assert "backtest" in channel.lower()

    def test_lock_value(self) -> None:
        """Test lock value generation."""
        value = lock_value()

        assert isinstance(value, str)
        assert ":" in value  # hostname:pid format
