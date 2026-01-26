"""Custom JSON logging handler for structured logging."""

import logging
from datetime import datetime
from typing import Any

from apps.trading.models.backtest import BacktestTasks
from apps.trading.models.logs import TaskLog
from apps.trading.models.trading import TradingTasks


class JSONLoggingHandler(logging.Handler):
    """
    Custom logging handler that formats logs as JSON and persists to database.

    This handler intercepts log records, formats them as structured JSON,
    and persists them to the TaskLog model for queryable storage.
    """

    def __init__(self, task: BacktestTasks | TradingTasks) -> None:
        """
        Initialize the JSON logging handler.

        Args:
            task: The task instance (BacktestTasks or TradingTasks) to associate logs with
        """
        super().__init__()
        self.task = task

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record as JSON and persist to database.

        Formats the log record as a structured JSON entry and saves it to the
        TaskLog model with task context.

        Args:
            record: The log record to emit
        """
        try:
            # Extract extra context from record if present
            context = {}
            if hasattr(record, "__dict__"):
                # Get all custom attributes added via extra parameter
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "taskName",
                    ]:
                        context[key] = value

            # Build structured log entry
            log_entry: dict[str, Any] = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "task_id": str(self.task.pk),
                "task_type": ("backtest" if isinstance(self.task, BacktestTasks) else "trading"),
                "logger": record.name,
                "context": context,
            }

            # Persist to database
            TaskLog.objects.create(
                task_type=log_entry["task_type"],
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id,
                level=record.levelname,
                message=record.getMessage(),
                details=log_entry,
            )

        except Exception:
            # Prevent logging errors from breaking the application
            # Use handleError to report the issue through the logging system
            self.handleError(record)
