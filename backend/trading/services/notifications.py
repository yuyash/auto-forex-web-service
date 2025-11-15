"""
WebSocket notification utilities for task status updates.

This module provides functions for sending real-time notifications
via WebSocket channels for task status changes.

Requirements: 7.3, 7.4, 7.5
"""

import logging
from typing import Any

from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from trading.enums import TaskStatus

logger = logging.getLogger(__name__)


def send_task_status_notification(
    user_id: int,
    task_id: int,
    task_name: str,
    task_type: str,
    status: TaskStatus,
    execution_id: int | None = None,
    error_message: str | None = None,
) -> None:
    """
    Send task status update notification via WebSocket.

    Args:
        user_id: User ID who owns the task
        task_id: Task ID
        task_name: Task name
        task_type: Task type (backtest or trading)
        status: New task status
        execution_id: Execution ID if available
        error_message: Error message if task failed
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not available, skipping task status notification")
            return

        group_name = f"task_status_user_{user_id}"

        notification_data = {
            "task_id": task_id,
            "task_name": task_name,
            "task_type": task_type,
            "status": status,
            "execution_id": execution_id,
            "timestamp": timezone.now().isoformat(),
        }

        if error_message:
            notification_data["error_message"] = error_message

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "task_status_update",
                "data": notification_data,
            },
        )

        logger.info(
            "Task status notification sent: user=%s, task=%s, status=%s",
            user_id,
            task_id,
            status,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to send task status notification: %s", e, exc_info=True)


def send_execution_log_notification(
    task_type: str,
    task_id: int,
    execution_id: int,
    execution_number: int,
    log_entry: dict[str, Any],
) -> None:
    """
    Send log entry via WebSocket to connected clients.

    Args:
        task_type: Type of task (backtest or trading)
        task_id: Task ID
        execution_id: Execution ID
        execution_number: Execution number
        log_entry: Log entry dictionary with timestamp, level, and message
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = f"task_logs_{task_type}_{task_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "execution_log",
                "data": {
                    "execution_id": execution_id,
                    "task_id": task_id,
                    "task_type": task_type,
                    "execution_number": execution_number,
                    "log": log_entry,
                },
            },
        )
    except Exception:  # nosec B110  # pylint: disable=broad-exception-caught
        # Don't fail the execution if WebSocket notification fails
        pass


def send_execution_progress_notification(
    task_type: str,
    task_id: int,
    execution_id: int,
    progress: int,
    user_id: int,
) -> None:
    """
    Send progress update via WebSocket to connected clients.

    Args:
        task_type: Type of task (backtest or trading)
        task_id: Task ID
        execution_id: Execution ID
        progress: Progress percentage (0-100)
        user_id: User ID who owns the task
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = f"task_status_user_{user_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "task_progress_update",
                "data": {
                    "task_id": task_id,
                    "task_type": task_type,
                    "execution_id": execution_id,
                    "progress": progress,
                    "timestamp": timezone.now().isoformat(),
                },
            },
        )
    except Exception:  # nosec B110  # pylint: disable=broad-exception-caught
        # Don't fail the execution if WebSocket notification fails
        pass


def send_backtest_intermediate_results(
    task_id: int,
    execution_id: int,
    user_id: int,
    intermediate_results: dict[str, Any],
) -> None:
    """
    Send intermediate backtest results via WebSocket after each day is processed.

    Args:
        task_id: Task ID
        execution_id: Execution ID
        user_id: User ID who owns the task
        intermediate_results: Dictionary containing intermediate metrics and results
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = f"task_status_user_{user_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "backtest_intermediate_results",
                "data": {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": execution_id,
                    "timestamp": timezone.now().isoformat(),
                    **intermediate_results,
                },
            },
        )
    except Exception:  # nosec B110  # pylint: disable=broad-exception-caught
        # Don't fail the execution if WebSocket notification fails
        pass
