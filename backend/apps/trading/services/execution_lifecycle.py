"""Execution lifecycle side effects."""

from __future__ import annotations

from apps.trading.services.execution_snapshots import sync_execution_snapshot


def sync_terminal_execution_artifacts(*, task, task_type: str):
    """Persist terminal execution artifacts for a task run."""
    return sync_execution_snapshot(task=task, task_type=task_type)
