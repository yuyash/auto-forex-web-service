"""Shared Redis coordination key helpers for lifecycle tasks."""

from __future__ import annotations


def build_task_execution_instance_key(*, task_id: object, execution_id: object) -> str:
    """Build the execution-scoped Redis instance key for a task."""

    return f"{task_id}:{execution_id}"


def build_task_coordination_key(*, task_name: str, instance_key: object) -> str:
    """Build the Redis coordination key for a task instance."""

    return f"task:coord:{task_name}:{instance_key}"
