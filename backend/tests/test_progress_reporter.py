"""
Unit tests for ProgressReporter service.

Tests the ProgressReporter progress calculation and broadcasting including:
- Progress calculation accuracy
- Time estimation algorithm
- WebSocket message broadcasting
- Intermediate progress updates for large batches
- Mock WebSocket layer for isolated testing

Requirements: 1.1, 1.2, 1.3, 1.5
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.utils import timezone

import pytest

from trading.services.progress_reporter import ProgressReporter


@pytest.fixture
def progress_reporter():
    """Create a ProgressReporter instance with test data."""
    return ProgressReporter(
        task_id=1,
        execution_id=100,
        user_id=10,
        total_days=10,
    )


@pytest.fixture
def mock_notification():
    """Mock the WebSocket notification function."""
    with patch("trading.services.progress_reporter.send_execution_progress_notification") as mock:
        yield mock


class TestInitialization:
    """Test ProgressReporter initialization."""

    def test_init_sets_attributes(self):
        """Test that initialization sets all required attributes."""
        reporter = ProgressReporter(
            task_id=1,
            execution_id=100,
            user_id=10,
            total_days=5,
        )

        assert reporter.task_id == 1
        assert reporter.execution_id == 100
        assert reporter.user_id == 10
        assert reporter.total_days == 5
        assert reporter.completed_days == 0
        assert reporter.start_time is not None

    def test_init_records_start_time(self):
        """Test that initialization records start time."""
        before = timezone.now()
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=5)
        after = timezone.now()

        assert before <= reporter.start_time <= after


class TestProgressCalculation:
    """Test progress calculation accuracy."""

    def test_calculate_progress_zero_days(self, progress_reporter):
        """Test progress calculation with zero completed days."""
        progress = progress_reporter.calculate_progress(0)
        assert progress == 0

    def test_calculate_progress_partial_days(self, progress_reporter):
        """Test progress calculation with partial days."""
        # 2.5 days out of 10 = 25%
        progress = progress_reporter.calculate_progress(2.5)
        assert progress == 25

    def test_calculate_progress_all_days(self, progress_reporter):
        """Test progress calculation with all days completed."""
        progress = progress_reporter.calculate_progress(10)
        assert progress == 100

    def test_calculate_progress_exceeds_total(self, progress_reporter):
        """Test progress calculation when completed exceeds total (should clamp to 100)."""
        progress = progress_reporter.calculate_progress(15)
        assert progress == 100

    def test_calculate_progress_negative_days(self, progress_reporter):
        """Test progress calculation with negative days (should clamp to 0)."""
        progress = progress_reporter.calculate_progress(-1)
        assert progress == 0

    def test_calculate_progress_fractional_result(self, progress_reporter):
        """Test progress calculation with fractional result."""
        # 3 days out of 10 = 30%
        progress = progress_reporter.calculate_progress(3)
        assert progress == 30

        # 1 day out of 10 = 10%
        progress = progress_reporter.calculate_progress(1)
        assert progress == 10

    def test_calculate_progress_zero_total_days(self):
        """Test progress calculation when total_days is zero."""
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=0)
        progress = reporter.calculate_progress(0)
        assert progress == 100  # Should return 100% when no days to process


class TestTimeEstimation:
    """Test time estimation algorithm."""

    def test_estimate_remaining_time_zero_completed(self, progress_reporter):
        """Test time estimation with zero completed days."""
        remaining = progress_reporter.estimate_remaining_time(0, 100)
        assert remaining == 0.0

    def test_estimate_remaining_time_zero_elapsed(self, progress_reporter):
        """Test time estimation with zero elapsed time."""
        remaining = progress_reporter.estimate_remaining_time(5, 0)
        assert remaining == 0.0

    def test_estimate_remaining_time_linear_extrapolation(self, progress_reporter):
        """Test time estimation uses linear extrapolation."""
        # 2 days completed in 100 seconds = 50 seconds per day
        # 8 days remaining = 400 seconds
        remaining = progress_reporter.estimate_remaining_time(2, 100)
        assert remaining == 400.0

    def test_estimate_remaining_time_all_completed(self, progress_reporter):
        """Test time estimation when all days are completed."""
        remaining = progress_reporter.estimate_remaining_time(10, 500)
        assert remaining == 0.0

    def test_estimate_remaining_time_fractional_days(self, progress_reporter):
        """Test time estimation with fractional completed days."""
        # 2.5 days completed in 125 seconds = 50 seconds per day
        # 7.5 days remaining = 375 seconds
        remaining = progress_reporter.estimate_remaining_time(2.5, 125)
        assert remaining == 375.0

    def test_estimate_remaining_time_rounding(self, progress_reporter):
        """Test that time estimation rounds to 1 decimal place."""
        # 3 days in 100 seconds = 33.333... seconds per day
        # 7 days remaining = 233.333... seconds
        remaining = progress_reporter.estimate_remaining_time(3, 100)
        assert remaining == 233.3


class TestDayStartReporting:
    """Test report_day_start method."""

    def test_report_day_start_broadcasts_progress(self, progress_reporter, mock_notification):
        """Test that report_day_start broadcasts progress update."""
        current_day = datetime(2025, 11, 15, 10, 0, 0, tzinfo=UTC)

        progress_reporter.report_day_start(current_day, 0)

        # Verify WebSocket notification was called
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args

        assert call_args[1]["task_type"] == "backtest"
        assert call_args[1]["task_id"] == 1
        assert call_args[1]["execution_id"] == 100
        assert call_args[1]["progress"] == 0
        assert call_args[1]["user_id"] == 10

    def test_report_day_start_calculates_correct_progress(
        self, progress_reporter, mock_notification
    ):
        """Test that report_day_start calculates correct progress."""
        current_day = datetime(2025, 11, 15, 10, 0, 0, tzinfo=UTC)

        # Day 5 out of 10 = 50%
        progress_reporter.report_day_start(current_day, 5)

        call_args = mock_notification.call_args
        assert call_args[1]["progress"] == 50

    def test_report_day_start_handles_exception(self, progress_reporter, mock_notification):
        """Test that report_day_start handles exceptions gracefully."""
        mock_notification.side_effect = Exception("WebSocket error")
        current_day = datetime(2025, 11, 15, 10, 0, 0, tzinfo=UTC)

        # Should not raise exception
        progress_reporter.report_day_start(current_day, 0)


class TestDayProgressReporting:
    """Test report_day_progress method for intermediate updates."""

    def test_report_day_progress_broadcasts_update(self, progress_reporter, mock_notification):
        """Test that report_day_progress broadcasts intermediate update."""
        current_day = datetime(2025, 11, 15, 10, 0, 0, tzinfo=UTC)

        progress_reporter.report_day_progress(50000, 100000, current_day)

        # Verify WebSocket notification was called
        mock_notification.assert_called_once()

    def test_report_day_progress_calculates_overall_progress(
        self, progress_reporter, mock_notification
    ):
        """Test that report_day_progress calculates overall progress correctly."""
        # Completed 2 days, currently 50% through day 3
        # Overall: (2 + 0.5) / 10 = 25%
        progress_reporter.completed_days = 2

        progress_reporter.report_day_progress(50000, 100000)

        call_args = mock_notification.call_args
        assert call_args[1]["progress"] == 25

    def test_report_day_progress_zero_total_ticks(self, progress_reporter, mock_notification):
        """Test report_day_progress with zero total ticks (should not broadcast)."""
        progress_reporter.report_day_progress(0, 0)

        # Should not call notification when total_ticks is 0
        mock_notification.assert_not_called()

    def test_report_day_progress_handles_exception(self, progress_reporter, mock_notification):
        """Test that report_day_progress handles exceptions gracefully."""
        mock_notification.side_effect = Exception("WebSocket error")

        # Should not raise exception
        progress_reporter.report_day_progress(50000, 100000)


class TestDayCompleteReporting:
    """Test report_day_complete method."""

    def test_report_day_complete_updates_completed_days(self, progress_reporter, mock_notification):
        """Test that report_day_complete updates completed_days counter."""
        progress_reporter.report_day_complete(0, 10.5)

        assert progress_reporter.completed_days == 1

    def test_report_day_complete_broadcasts_progress(self, progress_reporter, mock_notification):
        """Test that report_day_complete broadcasts progress update."""
        progress_reporter.report_day_complete(2, 15.3)

        # Verify WebSocket notification was called
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args

        assert call_args[1]["task_type"] == "backtest"
        assert call_args[1]["task_id"] == 1
        assert call_args[1]["execution_id"] == 100
        assert call_args[1]["progress"] == 30  # 3 days out of 10
        assert call_args[1]["user_id"] == 10

    def test_report_day_complete_multiple_days(self, progress_reporter, mock_notification):
        """Test report_day_complete for multiple days."""
        # Complete day 0
        progress_reporter.report_day_complete(0, 10.0)
        assert progress_reporter.completed_days == 1

        # Complete day 1
        progress_reporter.report_day_complete(1, 12.0)
        assert progress_reporter.completed_days == 2

        # Complete day 2
        progress_reporter.report_day_complete(2, 11.5)
        assert progress_reporter.completed_days == 3

        # Verify final progress
        call_args = mock_notification.call_args
        assert call_args[1]["progress"] == 30  # 3 out of 10

    def test_report_day_complete_handles_exception(self, progress_reporter, mock_notification):
        """Test that report_day_complete handles exceptions gracefully."""
        mock_notification.side_effect = Exception("WebSocket error")

        # Should not raise exception
        progress_reporter.report_day_complete(0, 10.0)

        # Should still update completed_days
        assert progress_reporter.completed_days == 1


class TestElapsedTime:
    """Test elapsed time calculation."""

    def test_elapsed_time_increases(self, progress_reporter):
        """Test that elapsed time increases over time."""
        import time

        elapsed1 = progress_reporter._elapsed_time()
        time.sleep(0.1)
        elapsed2 = progress_reporter._elapsed_time()

        assert elapsed2 > elapsed1
        assert elapsed2 - elapsed1 >= 0.1

    def test_elapsed_time_starts_at_zero(self):
        """Test that elapsed time starts near zero."""
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=5)
        elapsed = reporter._elapsed_time()

        # Should be very close to 0 (within 1 second)
        assert 0 <= elapsed < 1.0


class TestBroadcastProgress:
    """Test WebSocket broadcasting."""

    def test_broadcast_progress_calls_notification_service(
        self, progress_reporter, mock_notification
    ):
        """Test that _broadcast_progress calls the notification service."""
        metadata = {"test_key": "test_value"}

        progress_reporter._broadcast_progress(50, metadata)

        mock_notification.assert_called_once_with(
            task_type="backtest",
            task_id=1,
            execution_id=100,
            progress=50,
            user_id=10,
        )

    def test_broadcast_progress_handles_exception(self, progress_reporter, mock_notification):
        """Test that _broadcast_progress handles exceptions gracefully."""
        mock_notification.side_effect = Exception("WebSocket error")

        # Should not raise exception
        progress_reporter._broadcast_progress(50, {})


class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    def test_complete_backtest_workflow(self, mock_notification):
        """Test complete backtest workflow with progress reporting."""
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=3)

        # Day 1
        day1 = datetime(2025, 11, 15, 0, 0, 0, tzinfo=UTC)
        reporter.report_day_start(day1, 0)
        reporter.report_day_complete(0, 10.0)

        # Day 2
        day2 = datetime(2025, 11, 16, 0, 0, 0, tzinfo=UTC)
        reporter.report_day_start(day2, 1)
        reporter.report_day_complete(1, 12.0)

        # Day 3
        day3 = datetime(2025, 11, 17, 0, 0, 0, tzinfo=UTC)
        reporter.report_day_start(day3, 2)
        reporter.report_day_complete(2, 11.0)

        # Verify final state
        assert reporter.completed_days == 3
        assert reporter.calculate_progress(3) == 100

        # Verify notifications were sent (2 per day: start + complete)
        assert mock_notification.call_count == 6

    def test_large_batch_with_intermediate_updates(self, mock_notification):
        """Test large batch processing with intermediate progress updates."""
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=5)

        # Start day with large tick count
        day1 = datetime(2025, 11, 15, 0, 0, 0, tzinfo=UTC)
        reporter.report_day_start(day1, 0)

        # Report intermediate progress at 25%, 50%, 75%
        reporter.report_day_progress(25000, 100000, day1)
        reporter.report_day_progress(50000, 100000, day1)
        reporter.report_day_progress(75000, 100000, day1)

        # Complete day
        reporter.report_day_complete(0, 50.0)

        # Verify notifications: 1 start + 3 intermediate + 1 complete = 5
        assert mock_notification.call_count == 5

    def test_time_estimation_accuracy(self, mock_notification):
        """Test time estimation becomes more accurate over time."""
        reporter = ProgressReporter(task_id=1, execution_id=100, user_id=10, total_days=10)

        # Simulate consistent processing time per day
        import time

        for day_index in range(5):
            day = datetime(2025, 11, 15, 0, 0, 0, tzinfo=UTC) + timedelta(days=day_index)
            reporter.report_day_start(day, day_index)

            # Simulate 10 seconds per day
            time.sleep(0.01)  # Use small sleep for test speed

            reporter.report_day_complete(day_index, 10.0)

        # After 5 days, estimate should be reasonable
        elapsed = reporter._elapsed_time()
        remaining = reporter.estimate_remaining_time(5, elapsed)

        # Should estimate time for remaining 5 days
        assert remaining > 0
        # Rough check: should be approximately equal to elapsed time
        # (since we're halfway through)
        assert 0.5 * elapsed <= remaining <= 2 * elapsed
