"""Logger factory for creating task-specific loggers with JSON formatting."""

import logging

from apps.trading.models.backtest import BacktestTasks
from apps.trading.models.trading import TradingTasks
from apps.trading.services.logging.handler import JSONLoggingHandler


def get_task_logger(
    task: BacktestTasks | TradingTasks,
    logger_name: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Get a logger configured with JSONLoggingHandler for a task.

    This factory function creates or retrieves a logger configured with the
    JSONLoggingHandler for structured JSON logging. The logger is configured
    with the specified log level and prevents duplicate handlers if called
    multiple times for the same logger.

    Args:
        task: The task instance (BacktestTasks or TradingTasks) to associate logs with
        logger_name: Optional logger name. If not provided, defaults to a unique name
                    based on task type and ID (e.g., "backtest.550e8400-e29b-41d4-a716-446655440000")
        level: Log level (defaults to INFO). Use logging.DEBUG, logging.INFO,
              logging.WARNING, logging.ERROR, or logging.CRITICAL

    Returns:
        Configured logger instance with JSONLoggingHandler attached

    Example:
        >>> task = BacktestTasks.objects.get(pk=task_id)
        >>> logger = get_task_logger(task, level=logging.DEBUG)
        >>> logger.info("Strategy started", extra={"instrument": "USD_JPY"})
    """
    # Generate default logger name if not provided
    if logger_name is None:
        task_type = "backtest" if isinstance(task, BacktestTasks) else "trading"
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
