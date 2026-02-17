"""Task logging with structured JSON formatting and database persistence.

This module provides custom logging infrastructure for trading tasks, including:
- JSONLoggingHandler: Custom handler that persists logs to database
- get_task_logger: Factory function for creating task-specific loggers
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from apps.trading.models.logs import TaskLog

if TYPE_CHECKING:
    from apps.trading.models import BacktestTask, TradingTask


DEFAULT_TASK_LOGGER_NAMES: tuple[str, ...] = ("apps.trading",)


class JSONLoggingHandler(logging.Handler):
    """Custom logging handler that formats logs as JSON and persists to database.

    This handler intercepts log records, formats them as structured JSON,
    and persists them to the TaskLog model for queryable storage.
    """

    def __init__(self, task: BacktestTask | TradingTask) -> None:
        """Initialize the JSON logging handler.

        Args:
            task: The task instance (BacktestTask or TradingTask) to associate logs with
        """
        super().__init__()
        self.task = task

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record as JSON and persist to database.

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

            # Determine task type
            from apps.trading.models import BacktestTask

            task_type = "backtest" if isinstance(self.task, BacktestTask) else "trading"

            # Build structured log entry
            log_entry: dict[str, Any] = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "task_id": str(self.task.pk),
                "task_type": task_type,
                "logger": record.name,
                "context": context,
            }

            # Persist to database
            TaskLog.objects.create(
                task_type=task_type,
                task_id=self.task.pk,
                celery_task_id=self.task.celery_task_id,
                level=record.levelname,
                component=record.name,
                message=record.getMessage(),
                details=log_entry,
            )

        except Exception:
            # Prevent logging errors from breaking the application
            # Use handleError to report the issue through the logging system
            self.handleError(record)


def get_task_logger(
    task: BacktestTask | TradingTask,
    logger_name: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Get a logger configured with JSONLoggingHandler for a task.

    This factory function creates or retrieves a logger configured with the
    JSONLoggingHandler for structured JSON logging. The logger is configured
    with the specified log level and prevents duplicate handlers if called
    multiple times for the same logger.

    Args:
        task: The task instance (BacktestTask or TradingTask) to associate logs with
        logger_name: Optional logger name. If not provided, defaults to a unique name
                    based on task type and ID (e.g., "backtest.550e8400-e29b-41d4-a716-446655440000")
        level: Log level (defaults to INFO). Use logging.DEBUG, logging.INFO,
              logging.WARNING, logging.ERROR, or logging.CRITICAL

    Returns:
        Configured logger instance with JSONLoggingHandler attached

    Example:
        >>> task = BacktestTask.objects.get(pk=task_id)
        >>> logger = get_task_logger(task, level=logging.DEBUG)
        >>> logger.info("Processing tick", extra={"tick_count": 1000})
    """
    from apps.trading.models import BacktestTask

    # Generate default logger name if not provided
    if logger_name is None:
        task_type = "backtest" if isinstance(task, BacktestTask) else "trading"
        logger_name = f"{task_type}.{task.pk}"

    # Get or create logger
    logger = logging.getLogger(logger_name)

    # Set log level
    logger.setLevel(level)

    # Check if JSONLoggingHandler is already attached to prevent duplicates
    has_json_handler = any(
        isinstance(handler, JSONLoggingHandler) and handler.task.pk == task.pk
        for handler in logger.handlers
    )

    # Add JSONLoggingHandler if not already present
    if not has_json_handler:
        handler = JSONLoggingHandler(task)
        handler.setLevel(level)
        logger.addHandler(handler)

    return logger


class TaskLoggingSession:
    """Attach JSON task logging handlers for a single task execution.

    This centralizes logger wiring so individual modules do not need to manage
    handler registration directly.
    """

    def __init__(
        self,
        task: BacktestTask | TradingTask,
        *,
        level: int = logging.INFO,
        logger_names: Sequence[str] | None = None,
        extra_logger_names: Sequence[str] | None = None,
    ) -> None:
        self.task = task
        self.level = level
        self.logger_names = tuple(logger_names or DEFAULT_TASK_LOGGER_NAMES)
        self.extra_logger_names = tuple(extra_logger_names or ())
        self.handler = JSONLoggingHandler(task)
        self.handler.setLevel(level)
        self._attached_loggers: list[logging.Logger] = []

    def start(self) -> None:
        """Attach handler to configured loggers (idempotent)."""
        all_logger_names = tuple(dict.fromkeys((*self.logger_names, *self.extra_logger_names)))

        for name in all_logger_names:
            logger_obj = logging.getLogger(name)

            # Avoid duplicate writes for the same task logger pair.
            has_same_task_handler = any(
                isinstance(h, JSONLoggingHandler)
                and (task := getattr(h, "task", None)) is not None
                and task.pk == self.task.pk
                for h in logger_obj.handlers
            )
            if has_same_task_handler:
                continue

            logger_obj.addHandler(self.handler)
            self._attached_loggers.append(logger_obj)

    def stop(self) -> None:
        """Detach handler from loggers where it was attached."""
        for logger_obj in self._attached_loggers:
            if self.handler in logger_obj.handlers:
                logger_obj.removeHandler(self.handler)
        self._attached_loggers.clear()

    def __enter__(self) -> TaskLoggingSession:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any | None,
    ) -> bool:
        self.stop()
        return False
