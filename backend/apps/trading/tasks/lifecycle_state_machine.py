"""Shared task lifecycle transition rules.

This module centralises allowed source states per lifecycle command so API
and worker-side orchestration stay consistent.
"""

from __future__ import annotations

from apps.trading.enums import TaskStatus

ALLOWED_STATUS_BY_COMMAND: dict[str, tuple[TaskStatus, ...]] = {
    "start": (TaskStatus.CREATED,),
    "stop": (
        TaskStatus.STARTING,
        TaskStatus.RUNNING,
        TaskStatus.PAUSED,
        TaskStatus.IDLE,
        TaskStatus.STOPPING,
        TaskStatus.DRAINING,
    ),
    "pause": (TaskStatus.STARTING, TaskStatus.RUNNING),
    "resume_backtest": (TaskStatus.PAUSED, TaskStatus.STOPPED),
    "resume_trading": (TaskStatus.PAUSED, TaskStatus.STOPPED, TaskStatus.FAILED),
    "restart": (
        TaskStatus.CREATED,
        TaskStatus.STARTING,
        TaskStatus.RUNNING,
        TaskStatus.PAUSED,
        TaskStatus.STOPPING,
        TaskStatus.STOPPED,
        TaskStatus.DRAINING,
        TaskStatus.IDLE,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    ),
}


def allowed_statuses_for_command(command: str) -> tuple[TaskStatus, ...]:
    """Return allowed source statuses for *command*."""
    return ALLOWED_STATUS_BY_COMMAND.get(command, ())
