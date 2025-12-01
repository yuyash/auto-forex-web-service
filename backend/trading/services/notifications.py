"""
Legacy notification utilities for task status updates.

This module previously provided WebSocket notifications for task status changes.
These functions are now deprecated as the system has migrated to HTTP polling.
Functions are kept for backward compatibility but do nothing.

Requirements: 7.3, 7.4, 7.5
"""

import logging
from typing import Any

from trading.enums import TaskStatus

logger = logging.getLogger(__name__)


def send_task_status_notification(
    user_id: int,
    task_id: int,
    task_name: str,  # pylint: disable=unused-argument
    task_type: str,  # pylint: disable=unused-argument
    status: TaskStatus,
    execution_id: int | None = None,  # pylint: disable=unused-argument
    error_message: str | None = None,  # pylint: disable=unused-argument
    extra_data: dict[str, Any] | None = None,  # pylint: disable=unused-argument
) -> None:
    """
    Legacy function for task status notifications.

    This function is deprecated as task status updates are now retrieved via HTTP polling.
    Kept for backward compatibility but does nothing.

    Args:
        user_id: User ID who owns the task
        task_id: Task ID
        task_name: Task name (unused)
        task_type: Task type (unused)
        status: New task status
        execution_id: Execution ID if available (unused)
        error_message: Error message if task failed (unused)
        extra_data: Additional data to include in notification (unused)
    """
    # WebSocket notifications removed - task status is now retrieved via HTTP polling
    logger.debug(
        "Task status update (HTTP polling): user=%s, task=%s, status=%s",
        user_id,
        task_id,
        status,
    )


def send_execution_log_notification(
    task_type: str,  # pylint: disable=unused-argument
    task_id: int,  # pylint: disable=unused-argument
    execution_id: int,  # pylint: disable=unused-argument
    execution_number: int,  # pylint: disable=unused-argument
    log_entry: dict[str, Any],  # pylint: disable=unused-argument
    _user_id: int | None = None,
) -> None:
    """
    Legacy function for log notifications.

    This function is deprecated as logs are now stored in the database and retrieved via HTTP API.
    Kept for backward compatibility but does nothing.

    Args:
        task_type: Type of task (unused)
        task_id: Task ID (unused)
        execution_id: Execution ID (unused)
        execution_number: Execution number (unused)
        log_entry: Log entry dictionary (unused)
        _user_id: Optional user ID (unused)
    """
    # WebSocket notifications removed - logs are now stored in database and retrieved via HTTP API


def send_execution_progress_notification(
    task_type: str,  # pylint: disable=unused-argument
    task_id: int,  # pylint: disable=unused-argument
    execution_id: int,  # pylint: disable=unused-argument
    progress: int,  # pylint: disable=unused-argument
    user_id: int,  # pylint: disable=unused-argument
) -> None:
    """
    Legacy function for progress notifications.

    This function is deprecated as progress is now retrieved via HTTP polling.
    Kept for backward compatibility but does nothing.

    Args:
        task_type: Type of task (unused)
        task_id: Task ID (unused)
        execution_id: Execution ID (unused)
        progress: Progress percentage (unused)
        user_id: User ID (unused)
    """
    # WebSocket notifications removed - progress is now retrieved via HTTP polling


# Cache key for intermediate results
INTERMEDIATE_RESULTS_CACHE_KEY = "backtest:intermediate_results:{task_id}"
INTERMEDIATE_RESULTS_TTL = 300  # 5 minutes


def send_backtest_intermediate_results(
    task_id: int,
    execution_id: int,  # pylint: disable=unused-argument
    user_id: int,  # pylint: disable=unused-argument
    intermediate_results: dict[str, Any],
) -> None:
    """
    Store intermediate backtest results in cache for HTTP polling.

    This function stores the intermediate results in Redis cache so that
    the frontend can poll for live updates during backtest execution.

    Args:
        task_id: Task ID
        execution_id: Execution ID (unused, kept for backward compatibility)
        user_id: User ID (unused, kept for backward compatibility)
        intermediate_results: Intermediate metrics and results
    """
    from django.core.cache import cache

    cache_key = INTERMEDIATE_RESULTS_CACHE_KEY.format(task_id=task_id)
    cache.set(cache_key, intermediate_results, INTERMEDIATE_RESULTS_TTL)


def get_backtest_intermediate_results(task_id: int) -> dict[str, Any] | None:
    """
    Retrieve intermediate backtest results from cache.

    Args:
        task_id: Task ID

    Returns:
        Intermediate results dict or None if not available
    """
    from django.core.cache import cache

    cache_key = INTERMEDIATE_RESULTS_CACHE_KEY.format(task_id=task_id)
    result: dict[str, Any] | None = cache.get(cache_key)
    return result


def clear_backtest_intermediate_results(task_id: int) -> None:
    """
    Clear intermediate backtest results from cache.

    Should be called when backtest completes or fails.

    Args:
        task_id: Task ID
    """
    from django.core.cache import cache

    cache_key = INTERMEDIATE_RESULTS_CACHE_KEY.format(task_id=task_id)
    cache.delete(cache_key)
