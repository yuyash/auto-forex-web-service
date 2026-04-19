"""Unit tests for market tasks base utilities."""

from datetime import UTC, datetime

from apps.market.tasks.base import (
    backtest_stream_key_for_request,
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

    def test_backtest_stream_key_for_request(self) -> None:
        """Test backtest stream key generation."""
        request_id = "test-request-123"
        key = backtest_stream_key_for_request(request_id)

        assert "test-request-123" in key
        assert "backtest" in key.lower()
        assert "stream" in key.lower()

    def test_backtest_stream_key_scoped_by_execution_id(self) -> None:
        """Stream key includes the execution id when supplied."""
        task_id = "task-abc"
        exec_id = "exec-xyz"
        base_key = backtest_stream_key_for_request(task_id)
        scoped_key = backtest_stream_key_for_request(task_id, exec_id)

        assert scoped_key != base_key
        assert scoped_key.endswith(f"{task_id}:{exec_id}")
        assert scoped_key.startswith(base_key)

    def test_backtest_stream_key_execution_id_none_matches_legacy(self) -> None:
        """Passing ``None`` keeps the legacy task-id-only key."""
        task_id = "task-abc"

        assert backtest_stream_key_for_request(task_id) == backtest_stream_key_for_request(
            task_id, None
        )

    def test_lock_value(self) -> None:
        """Test lock value generation."""
        value = lock_value()

        assert isinstance(value, str)
        assert ":" in value  # hostname:pid format
