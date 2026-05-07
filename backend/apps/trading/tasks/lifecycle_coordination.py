"""Shared Redis coordination key helpers for lifecycle tasks."""

from __future__ import annotations

from typing import Final

TASK_COORDINATION_STATUS_FIELD: Final = "status"
TASK_COORDINATION_STOP_MODE_FIELD: Final = "stop_mode"


class TaskCoordinationStatus:
    """Redis coordination status values shared by lifecycle producers and consumers."""

    RUNNING: Final = "running"
    STOPPING: Final = "stopping"
    PAUSING: Final = "pausing"
    PAUSED: Final = "paused"
    STOPPED: Final = "stopped"
    COMPLETED: Final = "completed"
    FAILED: Final = "failed"


def build_task_execution_instance_key(*, task_id: object, execution_id: object) -> str:
    """Build the execution-scoped Redis instance key for a task."""

    return f"{task_id}:{execution_id}"


def build_task_coordination_key(*, task_name: str, instance_key: object) -> str:
    """Build the Redis coordination key for a task instance."""

    return f"task:coord:{task_name}:{instance_key}"
