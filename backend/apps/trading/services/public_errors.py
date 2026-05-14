"""Public error payload helpers for task APIs."""

from __future__ import annotations

from apps.trading.enums import TaskStatus

TASK_FAILED_ERROR_CODE = "TASK_EXECUTION_FAILED"
TASK_FAILED_PUBLIC_MESSAGE = "Task execution failed. Check server logs for details."


def task_public_error_message(status: str | None) -> str | None:
    """Return the fixed public error message for failed tasks."""
    if status == TaskStatus.FAILED:
        return TASK_FAILED_PUBLIC_MESSAGE
    return None


def task_public_error_code(status: str | None) -> str | None:
    """Return the stable public error code for failed tasks."""
    if status == TaskStatus.FAILED:
        return TASK_FAILED_ERROR_CODE
    return None
