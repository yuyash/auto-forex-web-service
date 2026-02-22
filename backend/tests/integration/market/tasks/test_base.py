"""Integration tests for task base utilities."""

from datetime import UTC, datetime

import pytest

from apps.market.tasks.base import (
    backtest_channel_for_request,
    isoformat,
    parse_iso_datetime,
)


@pytest.mark.django_db
class TestTaskBaseIntegration:
    """Integration tests for task base utilities."""

    def test_isoformat_with_timezone(self) -> None:
        """Test datetime to ISO format conversion."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        result = isoformat(dt)

        assert result.endswith("Z")
        assert "2024-01-15" in result
        assert "10:30:45" in result

    def test_parse_iso_datetime_roundtrip(self) -> None:
        """Test parsing and formatting roundtrip."""
        original = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        iso_str = isoformat(original)
        parsed = parse_iso_datetime(iso_str)

        assert parsed.year == original.year
        assert parsed.month == original.month
        assert parsed.day == original.day
        assert parsed.hour == original.hour

    def test_backtest_channel_generation(self) -> None:
        """Test backtest channel name generation."""
        request_id = "test-request-123"
        channel = backtest_channel_for_request(request_id)

        assert isinstance(channel, str)
        assert "test-request-123" in channel
        assert len(channel) > len(request_id)
