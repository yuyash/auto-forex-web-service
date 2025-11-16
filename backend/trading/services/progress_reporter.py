"""
Progress reporting service for backtest task execution.

This module provides the ProgressReporter class for calculating and broadcasting
real-time progress updates during backtest execution.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.5
"""

import logging
from datetime import datetime
from typing import Any

from django.utils import timezone

from trading.services.notifications import send_execution_progress_notification

logger = logging.getLogger(__name__)


class ProgressReporter:
    """
    Calculates and broadcasts task progress updates.

    This service tracks backtest execution progress on a day-by-day basis,
    calculates completion percentage, estimates remaining time, and broadcasts
    updates via WebSocket to connected frontend clients.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.5
    """

    def __init__(self, task_id: int, execution_id: int, user_id: int, total_days: int):
        """
        Initialize progress reporter with task context.

        Args:
            task_id: ID of the backtest task
            execution_id: ID of the task execution
            user_id: ID of the user who owns the task
            total_days: Total number of days to process

        Requirements: 5.1
        """
        self.task_id = task_id
        self.execution_id = execution_id
        self.user_id = user_id
        self.total_days = total_days
        self.start_time = timezone.now()
        self.completed_days = 0

        logger.info(
            "ProgressReporter initialized for task %d, execution %d: %d days",
            task_id,
            execution_id,
            total_days,
        )

    def report_day_start(self, current_day: datetime, day_index: int) -> None:
        """
        Report start of day batch processing.

        Broadcasts a progress update indicating which day is being processed
        and the total number of days remaining.

        Args:
            current_day: Date being processed
            day_index: Zero-based index of the current day

        Requirements: 1.1, 1.4, 1.5
        """
        try:
            progress = self.calculate_progress(day_index)
            estimated_time = self.estimate_remaining_time(day_index, self._elapsed_time())

            day_str = current_day.strftime("%Y-%m-%d")
            logger.info(
                "Task %d: Starting day %d/%d (%s) - Progress: %d%%",
                self.task_id,
                day_index + 1,
                self.total_days,
                day_str,
                progress,
            )

            # Broadcast progress update via WebSocket
            self._broadcast_progress(
                progress=progress,
                metadata={
                    "current_day": day_str,
                    "day_index": day_index,
                    "total_days": self.total_days,
                    "completed_days": day_index,
                    "estimated_time_remaining": estimated_time,
                    "phase": "day_start",
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to report day start: %s", e, exc_info=True)

    def report_day_progress(
        self, ticks_processed: int, total_ticks: int, current_day: datetime | None = None
    ) -> None:
        """
        Report intermediate progress within a day (for large batches).

        This method is called for days with >100k ticks to provide
        intermediate updates every 10% of completion within that day.

        Args:
            ticks_processed: Number of ticks processed so far in this day
            total_ticks: Total number of ticks for this day
            current_day: Optional date being processed

        Requirements: 1.3, 1.4, 1.5
        """
        try:
            if total_ticks == 0:
                return

            # Calculate within-day progress
            day_progress = (ticks_processed / total_ticks) * 100

            # Calculate overall progress (completed days + partial current day)
            partial_day = (ticks_processed / total_ticks) if total_ticks > 0 else 0
            overall_progress = self.calculate_progress(self.completed_days + partial_day)

            estimated_time = self.estimate_remaining_time(
                self.completed_days + partial_day, self._elapsed_time()
            )

            logger.debug(
                "Task %d: Day progress: %d/%d ticks (%.1f%%) - Overall: %d%%",
                self.task_id,
                ticks_processed,
                total_ticks,
                day_progress,
                overall_progress,
            )

            metadata: dict[str, Any] = {
                "completed_days": self.completed_days,
                "total_days": self.total_days,
                "ticks_processed": ticks_processed,
                "total_ticks": total_ticks,
                "day_progress": round(day_progress, 1),
                "estimated_time_remaining": estimated_time,
                "phase": "day_progress",
            }

            if current_day:
                metadata["current_day"] = current_day.strftime("%Y-%m-%d")

            # Broadcast intermediate progress
            self._broadcast_progress(progress=overall_progress, metadata=metadata)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to report day progress: %s", e, exc_info=True)

    def report_day_complete(self, day_index: int, processing_time: float) -> None:
        """
        Report completion of day batch.

        Updates the completed days counter and broadcasts progress update
        with timing metrics.

        Args:
            day_index: Zero-based index of the completed day
            processing_time: Time taken to process this day in seconds

        Requirements: 1.2, 1.4, 1.5, 5.2, 5.3
        """
        try:
            self.completed_days = day_index + 1
            progress = self.calculate_progress(self.completed_days)
            estimated_time = self.estimate_remaining_time(self.completed_days, self._elapsed_time())

            logger.info(
                "Task %d: Completed day %d/%d (%.2fs) - Progress: %d%%",
                self.task_id,
                self.completed_days,
                self.total_days,
                processing_time,
                progress,
            )

            # Broadcast progress update
            self._broadcast_progress(
                progress=progress,
                metadata={
                    "completed_days": self.completed_days,
                    "total_days": self.total_days,
                    "processing_time": round(processing_time, 2),
                    "estimated_time_remaining": estimated_time,
                    "phase": "day_complete",
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to report day complete: %s", e, exc_info=True)

    def calculate_progress(self, completed_days: float) -> int:
        """
        Calculate overall progress percentage.

        Progress is calculated as (completed_days / total_days) * 100.
        Supports fractional days for intermediate progress within a day.

        Args:
            completed_days: Number of completed days (can be fractional)

        Returns:
            Progress percentage (0-100)

        Requirements: 1.2, 5.2
        """
        if self.total_days == 0:
            return 100

        progress = (completed_days / self.total_days) * 100
        # Clamp to 0-100 range
        return max(0, min(100, int(progress)))

    def estimate_remaining_time(self, completed_days: float, elapsed_time: float) -> float:
        """
        Estimate time remaining based on current progress.

        Uses linear extrapolation: remaining_time = (elapsed_time / completed_days) * remaining_days

        Args:
            completed_days: Number of completed days (can be fractional)
            elapsed_time: Time elapsed since start in seconds

        Returns:
            Estimated remaining time in seconds (0 if cannot estimate)

        Requirements: 1.5
        """
        if completed_days <= 0 or elapsed_time <= 0:
            return 0.0

        remaining_days = self.total_days - completed_days
        if remaining_days <= 0:
            return 0.0

        # Calculate average time per day
        time_per_day = elapsed_time / completed_days

        # Estimate remaining time
        estimated_remaining = time_per_day * remaining_days

        return round(estimated_remaining, 1)

    def _elapsed_time(self) -> float:
        """
        Calculate elapsed time since start.

        Returns:
            Elapsed time in seconds
        """
        return (timezone.now() - self.start_time).total_seconds()

    def _broadcast_progress(
        self, progress: int, metadata: dict[str, Any]  # pylint: disable=unused-argument
    ) -> None:
        """
        Broadcast progress update via WebSocket.

        Args:
            progress: Progress percentage (0-100)
            metadata: Additional metadata to include in the message

        Requirements: 1.4
        """
        try:
            # Send via WebSocket notification service
            send_execution_progress_notification(
                task_type="backtest",
                task_id=self.task_id,
                execution_id=self.execution_id,
                progress=progress,
                user_id=self.user_id,
            )

            logger.debug(
                "Progress broadcast sent: task=%d, execution=%d, progress=%d%%",
                self.task_id,
                self.execution_id,
                progress,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to broadcast progress: %s", e, exc_info=True)
