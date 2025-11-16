"""
Unit tests for BacktestLogger service.

Tests the BacktestLogger structured logging and WebSocket broadcasting including:
- Log message formatting
- Progress indicator calculations
- ETA estimation accuracy
- Log levels are correct
- WebSocket broadcasting integration
- Mock send_execution_log_notification for isolated testing

Requirements: 6.1, 6.2, 6.3, 6.4, 6.7
"""

from unittest.mock import patch

import pytest

from trading.services.backtest_logger import BacktestLogger


@pytest.fixture
def backtest_logger():
    """Create a BacktestLogger instance with test data."""
    return BacktestLogger(
        task_id=123,
        execution_id=456,
        execution_number=1,
    )


@pytest.fixture
def mock_notification():
    """Mock the WebSocket notification function."""
    with patch("trading.services.backtest_logger.send_execution_log_notification") as mock:
        yield mock


@pytest.fixture
def mock_logger():
    """Mock the backend logger."""
    with patch("trading.services.backtest_logger.logging.getLogger") as mock:
        yield mock


class TestInitialization:
    """Test BacktestLogger initialization."""

    def test_init_sets_attributes(self):
        """Test that initialization sets all required attributes."""
        logger = BacktestLogger(
            task_id=123,
            execution_id=456,
            execution_number=1,
        )

        assert logger.task_id == 123
        assert logger.execution_id == 456
        assert logger.execution_number == 1
        assert logger.logger is not None


class TestLogExecutionStart:
    """Test log_execution_start method."""

    def test_logs_execution_start(self, backtest_logger, mock_notification):
        """Test that execution start is logged and broadcast."""
        backtest_logger.log_execution_start(total_days=3, date_range="2025-11-10 to 2025-11-12")

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args

        assert call_args[1]["task_type"] == "backtest"
        assert call_args[1]["task_id"] == 123
        assert call_args[1]["execution_id"] == 456
        assert call_args[1]["execution_number"] == 1

        log_entry = call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"
        assert "Starting backtest: 3 days" in log_entry["message"]
        assert "2025-11-10 to 2025-11-12" in log_entry["message"]
        assert log_entry["metadata"]["total_days"] == 3
        assert log_entry["metadata"]["date_range"] == "2025-11-10 to 2025-11-12"
        assert log_entry["metadata"]["phase"] == "execution_start"

    def test_message_format(self, backtest_logger, mock_notification):
        """Test that execution start message is formatted correctly."""
        backtest_logger.log_execution_start(total_days=5, date_range="2025-01-01 to 2025-01-05")

        log_entry = mock_notification.call_args[1]["log_entry"]
        expected_message = "Starting backtest: 5 days (2025-01-01 to 2025-01-05)"
        assert log_entry["message"] == expected_message


class TestLogDayStart:
    """Test log_day_start method."""

    def test_logs_day_start(self, backtest_logger, mock_notification):
        """Test that day start is logged and broadcast."""
        backtest_logger.log_day_start(day_index=0, total_days=3, date="2025-11-10")

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "INFO"
        assert "Day 1/3: 2025-11-10 - Fetching data..." in log_entry["message"]
        assert log_entry["metadata"]["day_index"] == 0
        assert log_entry["metadata"]["total_days"] == 3
        assert log_entry["metadata"]["date"] == "2025-11-10"
        assert log_entry["metadata"]["phase"] == "day_start"

    def test_day_index_formatting(self, backtest_logger, mock_notification):
        """Test that day index is displayed as 1-based."""
        backtest_logger.log_day_start(day_index=2, total_days=5, date="2025-11-12")

        log_entry = mock_notification.call_args[1]["log_entry"]
        assert "Day 3/5" in log_entry["message"]


class TestLogDayProcessing:
    """Test log_day_processing method."""

    def test_logs_day_processing(self, backtest_logger, mock_notification):
        """Test that day processing is logged and broadcast."""
        backtest_logger.log_day_processing(day_index=1, total_days=3, tick_count=520656)

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "INFO"
        assert "Day 2/3: Processing 520,656 ticks..." in log_entry["message"]
        assert log_entry["metadata"]["day_index"] == 1
        assert log_entry["metadata"]["total_days"] == 3
        assert log_entry["metadata"]["tick_count"] == 520656
        assert log_entry["metadata"]["phase"] == "day_processing"

    def test_tick_count_formatting(self, backtest_logger, mock_notification):
        """Test that tick count is formatted with commas."""
        backtest_logger.log_day_processing(day_index=0, total_days=1, tick_count=1234567)

        log_entry = mock_notification.call_args[1]["log_entry"]
        assert "1,234,567 ticks" in log_entry["message"]


class TestLogTickProgress:
    """Test log_tick_progress method with ETA calculation."""

    def test_logs_tick_progress(self, backtest_logger, mock_notification):
        """Test that tick progress is logged with ETA."""
        backtest_logger.log_tick_progress(
            processed=52065,
            total=520656,
            elapsed=5.0,
            day_index=0,
            total_days=3,
        )

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "INFO"
        assert "Day 1/3:" in log_entry["message"]
        assert "52,065/520,656" in log_entry["message"]
        assert log_entry["metadata"]["processed"] == 52065
        assert log_entry["metadata"]["total"] == 520656
        assert log_entry["metadata"]["phase"] == "tick_progress"

    def test_progress_percentage_calculation(self, backtest_logger, mock_notification):
        """Test that progress percentage is calculated correctly."""
        backtest_logger.log_tick_progress(
            processed=250000,
            total=500000,
            elapsed=10.0,
            day_index=0,
            total_days=1,
        )

        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["metadata"]["percent"] == 50.0
        assert "(50.0%)" in log_entry["message"]

    def test_rate_calculation(self, backtest_logger, mock_notification):
        """Test that processing rate is calculated correctly."""
        backtest_logger.log_tick_progress(
            processed=100000,
            total=500000,
            elapsed=10.0,
            day_index=0,
            total_days=1,
        )

        log_entry = mock_notification.call_args[1]["log_entry"]
        # Rate = 100000 / 10.0 = 10000 ticks/s
        assert log_entry["metadata"]["rate"] == 10000.0
        assert "10000 ticks/s" in log_entry["message"]

    def test_eta_calculation(self, backtest_logger, mock_notification):
        """Test that ETA is calculated correctly."""
        backtest_logger.log_tick_progress(
            processed=100000,
            total=500000,
            elapsed=10.0,
            day_index=0,
            total_days=1,
        )

        log_entry = mock_notification.call_args[1]["log_entry"]
        # ETA = (500000 - 100000) / (100000 / 10.0) = 400000 / 10000 = 40.0s
        assert log_entry["metadata"]["eta"] == 40.0
        assert "ETA: 40.0s" in log_entry["message"]

    def test_zero_total_ticks(self, backtest_logger, mock_notification):
        """Test that zero total ticks doesn't cause errors."""
        backtest_logger.log_tick_progress(
            processed=0,
            total=0,
            elapsed=1.0,
            day_index=0,
            total_days=1,
        )

        # Should not call notification for zero total
        mock_notification.assert_not_called()

    def test_zero_elapsed_time(self, backtest_logger, mock_notification):
        """Test that zero elapsed time doesn't cause division by zero."""
        backtest_logger.log_tick_progress(
            processed=1000,
            total=10000,
            elapsed=0.0,
            day_index=0,
            total_days=1,
        )

        log_entry = mock_notification.call_args[1]["log_entry"]
        # Rate should be 0 when elapsed is 0
        assert log_entry["metadata"]["rate"] == 0.0
        # ETA should be 0 when rate is 0
        assert log_entry["metadata"]["eta"] == 0.0

    def test_progress_bar_included(self, backtest_logger, mock_notification):
        """Test that progress bar is included in message."""
        backtest_logger.log_tick_progress(
            processed=250000,
            total=500000,
            elapsed=10.0,
            day_index=0,
            total_days=1,
        )

        log_entry = mock_notification.call_args[1]["log_entry"]
        # Progress bar should be present (contains █ and ░ characters)
        assert "█" in log_entry["message"] or "[" in log_entry["message"]


class TestLogDayComplete:
    """Test log_day_complete method."""

    def test_logs_day_complete(self, backtest_logger, mock_notification):
        """Test that day completion is logged and broadcast."""
        backtest_logger.log_day_complete(day_index=0, total_days=3, processing_time=50.123)

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "INFO"
        assert "Day 1/3: Complete (50.12s)" in log_entry["message"]
        assert log_entry["metadata"]["day_index"] == 0
        assert log_entry["metadata"]["total_days"] == 3
        assert log_entry["metadata"]["processing_time"] == 50.12
        assert log_entry["metadata"]["phase"] == "day_complete"

    def test_processing_time_rounding(self, backtest_logger, mock_notification):
        """Test that processing time is rounded to 2 decimal places."""
        backtest_logger.log_day_complete(day_index=0, total_days=1, processing_time=123.456789)

        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["metadata"]["processing_time"] == 123.46


class TestLogExecutionComplete:
    """Test log_execution_complete method."""

    def test_logs_execution_complete(self, backtest_logger, mock_notification):
        """Test that execution completion is logged and broadcast."""
        backtest_logger.log_execution_complete(total_time=150.5, total_trades=42)

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "INFO"
        assert "Backtest complete: 150.50s | 42 trades" in log_entry["message"]
        assert log_entry["metadata"]["total_time"] == 150.5
        assert log_entry["metadata"]["total_trades"] == 42
        assert log_entry["metadata"]["phase"] == "execution_complete"


class TestLogError:
    """Test log_error method."""

    def test_logs_error_message(self, backtest_logger, mock_notification):
        """Test that error messages are logged correctly."""
        backtest_logger.log_error("Something went wrong")

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "ERROR"
        assert log_entry["message"] == "Something went wrong"
        assert log_entry["metadata"]["phase"] == "error"

    def test_logs_error_with_exception(self, backtest_logger, mock_notification):
        """Test that errors with exceptions include exception details."""
        error = ValueError("Invalid value")
        backtest_logger.log_error("Processing failed", error=error)

        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "ERROR"
        assert log_entry["message"] == "Processing failed"
        assert log_entry["metadata"]["error_type"] == "ValueError"
        assert log_entry["metadata"]["error_details"] == "Invalid value"

    def test_logs_error_with_metadata(self, backtest_logger, mock_notification):
        """Test that errors can include additional metadata."""
        backtest_logger.log_error("Data error", day_index=5, tick_position=12345)

        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["metadata"]["day_index"] == 5
        assert log_entry["metadata"]["tick_position"] == 12345


class TestLogWarning:
    """Test log_warning method."""

    def test_logs_warning_message(self, backtest_logger, mock_notification):
        """Test that warning messages are logged correctly."""
        backtest_logger.log_warning("This is a warning")

        # Verify WebSocket notification was sent
        mock_notification.assert_called_once()
        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["level"] == "WARNING"
        assert log_entry["message"] == "This is a warning"
        assert log_entry["metadata"]["phase"] == "warning"

    def test_logs_warning_with_metadata(self, backtest_logger, mock_notification):
        """Test that warnings can include additional metadata."""
        backtest_logger.log_warning("Low data quality", quality_score=0.5)

        log_entry = mock_notification.call_args[1]["log_entry"]

        assert log_entry["metadata"]["quality_score"] == 0.5


class TestLogAndBroadcast:
    """Test _log_and_broadcast helper method."""

    def test_broadcasts_to_websocket(self, backtest_logger, mock_notification):
        """Test that messages are broadcast via WebSocket."""
        backtest_logger._log_and_broadcast(
            level="INFO",
            message="Test message",
            metadata={"key": "value"},
        )

        # Verify WebSocket notification was called
        mock_notification.assert_called_once()
        call_kwargs = mock_notification.call_args[1]
        assert call_kwargs["task_type"] == "backtest"
        assert call_kwargs["task_id"] == 123
        assert call_kwargs["execution_id"] == 456
        assert call_kwargs["execution_number"] == 1
        assert call_kwargs["log_entry"]["level"] == "INFO"
        assert call_kwargs["log_entry"]["message"] == "Test message"
        assert call_kwargs["log_entry"]["metadata"] == {"key": "value"}
        assert "timestamp" in call_kwargs["log_entry"]

    def test_includes_timestamp(self, backtest_logger, mock_notification):
        """Test that log entries include timestamp."""
        backtest_logger._log_and_broadcast(level="INFO", message="Test")

        log_entry = mock_notification.call_args[1]["log_entry"]
        assert "timestamp" in log_entry
        # Timestamp should be in ISO format
        assert "T" in log_entry["timestamp"]

    def test_handles_broadcast_failure(self, backtest_logger):
        """Test that broadcast failures don't crash execution."""
        with patch(
            "trading.services.backtest_logger.send_execution_log_notification",
            side_effect=Exception("WebSocket error"),
        ):
            # Should not raise exception
            backtest_logger._log_and_broadcast(level="INFO", message="Test")


class TestProgressBar:
    """Test _create_progress_bar method."""

    def test_creates_progress_bar_0_percent(self, backtest_logger):
        """Test progress bar at 0%."""
        bar = backtest_logger._create_progress_bar(0, width=10)
        assert bar == "[░░░░░░░░░░] 0.0%"

    def test_creates_progress_bar_50_percent(self, backtest_logger):
        """Test progress bar at 50%."""
        bar = backtest_logger._create_progress_bar(50, width=10)
        assert bar == "[█████░░░░░] 50.0%"

    def test_creates_progress_bar_100_percent(self, backtest_logger):
        """Test progress bar at 100%."""
        bar = backtest_logger._create_progress_bar(100, width=10)
        assert bar == "[██████████] 100.0%"

    def test_creates_progress_bar_custom_width(self, backtest_logger):
        """Test progress bar with custom width."""
        bar = backtest_logger._create_progress_bar(25, width=20)
        # 25% of 20 = 5 filled, 15 empty
        assert bar == "[█████░░░░░░░░░░░░░░░] 25.0%"

    def test_progress_bar_fractional_percent(self, backtest_logger):
        """Test progress bar with fractional percentage."""
        bar = backtest_logger._create_progress_bar(33.3, width=10)
        # 33.3% of 10 = 3 filled, 7 empty
        assert bar == "[███░░░░░░░] 33.3%"


class TestLogLevels:
    """Test that correct log levels are used."""

    def test_execution_start_uses_info(self, backtest_logger, mock_notification):
        """Test that execution start uses INFO level."""
        backtest_logger.log_execution_start(1, "2025-11-10 to 2025-11-10")
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_day_start_uses_info(self, backtest_logger, mock_notification):
        """Test that day start uses INFO level."""
        backtest_logger.log_day_start(0, 1, "2025-11-10")
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_day_processing_uses_info(self, backtest_logger, mock_notification):
        """Test that day processing uses INFO level."""
        backtest_logger.log_day_processing(0, 1, 1000)
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_tick_progress_uses_info(self, backtest_logger, mock_notification):
        """Test that tick progress uses INFO level."""
        backtest_logger.log_tick_progress(100, 1000, 1.0, 0, 1)
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_day_complete_uses_info(self, backtest_logger, mock_notification):
        """Test that day complete uses INFO level."""
        backtest_logger.log_day_complete(0, 1, 10.0)
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_execution_complete_uses_info(self, backtest_logger, mock_notification):
        """Test that execution complete uses INFO level."""
        backtest_logger.log_execution_complete(100.0, 10)
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "INFO"

    def test_error_uses_error_level(self, backtest_logger, mock_notification):
        """Test that log_error uses ERROR level."""
        backtest_logger.log_error("Error message")
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "ERROR"

    def test_warning_uses_warning_level(self, backtest_logger, mock_notification):
        """Test that log_warning uses WARNING level."""
        backtest_logger.log_warning("Warning message")
        log_entry = mock_notification.call_args[1]["log_entry"]
        assert log_entry["level"] == "WARNING"
