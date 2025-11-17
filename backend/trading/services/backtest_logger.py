"""
Enhanced logging service for backtest task execution with WebSocket streaming.

This module provides the BacktestLogger class for structured logging with
real-time log streaming to frontend clients via WebSocket.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

import logging
from typing import Any

from django.utils import timezone

from trading.services.notifications import send_execution_log_notification

logger = logging.getLogger(__name__)


class BacktestLogger:
    """
    Enhanced logger with structured logging and WebSocket broadcasting.

    This service provides structured logging for backtest execution with
    real-time streaming to frontend clients. All log entries are both
    written to backend logs and broadcast via WebSocket.

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
    """

    def __init__(
        self, task_id: int, execution_id: int, execution_number: int, user_id: int | None = None
    ):
        """
        Initialize backtest logger with task context.

        Args:
            task_id: ID of the backtest task
            execution_id: ID of the task execution
            execution_number: Execution number for display
            user_id: Optional user ID for WebSocket log streaming

        Requirements: 6.1, 6.7
        """
        self.task_id = task_id
        self.execution_id = execution_id
        self.execution_number = execution_number
        self.user_id = user_id
        self.logger = logging.getLogger(f"backtest.{task_id}")

        # Disable propagation to prevent duplicate logs from parent loggers
        # This ensures each log message is only emitted once
        self.logger.propagate = False

        # Ensure logger has at least one handler to prevent "No handlers" warning
        # The handler is only for backend logging; WebSocket streaming is separate
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(handler)

    def log_execution_start(self, total_days: int, date_range: str) -> None:
        """
        Log backtest execution start with date range.

        Args:
            total_days: Total number of days to process
            date_range: Date range string (e.g., "2025-11-10 to 2025-11-12")

        Requirements: 6.1, 6.6
        """
        message = f"Starting backtest: {total_days} days ({date_range})"
        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "total_days": total_days,
                "date_range": date_range,
                "phase": "execution_start",
            },
        )

    def log_day_start(self, day_index: int, total_days: int, date: str) -> None:
        """
        Log day batch start with day index.

        Args:
            day_index: Zero-based index of the current day
            total_days: Total number of days to process
            date: Date string (e.g., "2025-11-10")

        Requirements: 6.1, 6.6
        """
        message = f"Day {day_index + 1}/{total_days}: {date} - Fetching data..."
        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "day_index": day_index,
                "total_days": total_days,
                "date": date,
                "phase": "day_start",
            },
        )

    def log_day_processing(self, day_index: int, total_days: int, tick_count: int) -> None:
        """
        Log day processing with tick count.

        Args:
            day_index: Zero-based index of the current day
            total_days: Total number of days to process
            tick_count: Number of ticks to process for this day

        Requirements: 6.1, 6.6
        """
        message = f"Day {day_index + 1}/{total_days}: Processing {tick_count:,} ticks..."
        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "day_index": day_index,
                "total_days": total_days,
                "tick_count": tick_count,
                "phase": "day_processing",
            },
        )

    def log_tick_progress(
        self, processed: int, total: int, elapsed: float, day_index: int, total_days: int
    ) -> None:
        """
        Log tick processing progress with ETA calculation.

        This method is called for large batches (>100k ticks) to provide
        intermediate progress updates every 10% of completion.

        Args:
            processed: Number of ticks processed so far
            total: Total number of ticks for this day
            elapsed: Time elapsed in seconds
            day_index: Zero-based index of the current day
            total_days: Total number of days to process

        Requirements: 6.2, 6.3, 6.4
        """
        if total == 0:
            return

        # Calculate progress metrics
        percent = (processed / total) * 100
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0

        # Create visual progress indicator
        progress_bar = self._create_progress_bar(percent)

        message = (
            f"Day {day_index + 1}/{total_days}: {progress_bar} "
            f"{processed:,}/{total:,} ({percent:.1f}%) | "
            f"Rate: {rate:.0f} ticks/s | ETA: {eta:.1f}s"
        )

        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "day_index": day_index,
                "total_days": total_days,
                "processed": processed,
                "total": total,
                "percent": round(percent, 1),
                "rate": round(rate, 0),
                "eta": round(eta, 1),
                "phase": "tick_progress",
            },
        )

    def log_day_complete(self, day_index: int, total_days: int, processing_time: float) -> None:
        """
        Log day batch completion with timing.

        Args:
            day_index: Zero-based index of the completed day
            total_days: Total number of days to process
            processing_time: Time taken to process this day in seconds

        Requirements: 6.4, 6.6
        """
        message = f"Day {day_index + 1}/{total_days}: Complete ({processing_time:.2f}s)"
        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "day_index": day_index,
                "total_days": total_days,
                "processing_time": round(processing_time, 2),
                "phase": "day_complete",
            },
        )

    def log_execution_complete(self, total_time: float, total_trades: int) -> None:
        """
        Log backtest execution completion with summary.

        Args:
            total_time: Total execution time in seconds
            total_trades: Total number of trades executed

        Requirements: 6.6
        """
        message = f"Backtest complete: {total_time:.2f}s | {total_trades} trades"
        self._log_and_broadcast(
            level="INFO",
            message=message,
            metadata={
                "total_time": round(total_time, 2),
                "total_trades": total_trades,
                "phase": "execution_complete",
            },
        )

    def log_error(self, message: str, error: Exception | None = None, **kwargs: Any) -> None:
        """
        Log error message with optional exception details.

        Args:
            message: Error message
            error: Optional exception object
            **kwargs: Additional metadata to include

        Requirements: 6.5, 6.6
        """
        metadata = {"phase": "error", **kwargs}

        if error:
            metadata["error_type"] = type(error).__name__
            metadata["error_details"] = str(error)

        self._log_and_broadcast(level="ERROR", message=message, metadata=metadata)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        """
        Log warning message.

        Args:
            message: Warning message
            **kwargs: Additional metadata to include

        Requirements: 6.6
        """
        metadata = {"phase": "warning", **kwargs}
        self._log_and_broadcast(level="WARNING", message=message, metadata=metadata)

    def _log_and_broadcast(
        self, level: str, message: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Helper that logs to backend AND broadcasts to frontend.

        This method ensures all log entries are both written to backend logs
        and streamed to frontend clients via WebSocket.

        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            metadata: Optional metadata dictionary

        Requirements: 6.7
        """
        try:
            # Format message with task/execution context
            formatted_message = f"[Task {self.task_id} | Execution {self.execution_id}] {message}"

            # Log to backend
            log_method = getattr(self.logger, level.lower())
            log_method(formatted_message)

            # Create log entry for WebSocket broadcast
            log_entry: dict[str, Any] = {
                "timestamp": timezone.now().isoformat(),
                "level": level,
                "message": message,
            }

            # Add metadata if provided
            if metadata:
                log_entry["metadata"] = metadata

            # Broadcast to frontend via WebSocket
            send_execution_log_notification(
                task_type="backtest",
                task_id=self.task_id,
                execution_id=self.execution_id,
                execution_number=self.execution_number,
                log_entry=log_entry,
                _user_id=self.user_id,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Don't fail execution if logging fails
            logger.error(
                "Failed to log and broadcast message: %s (original message: %s)",
                e,
                message,
                exc_info=True,
            )

    def _create_progress_bar(self, percent: float, width: int = 20) -> str:
        """
        Create a visual progress bar indicator.

        Args:
            percent: Progress percentage (0-100)
            width: Width of the progress bar in characters

        Returns:
            Progress bar string (e.g., "[████████░░░░░░░░░░░░] 40.0%")

        Requirements: 6.3
        """
        filled = int((percent / 100) * width)
        empty = width - filled
        progress_bar = "█" * filled + "░" * empty
        return f"[{progress_bar}] {percent:.1f}%"
