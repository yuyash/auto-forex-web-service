"""Unit tests for lifecycle Redis coordination helpers."""

from __future__ import annotations

from uuid import uuid4

from apps.trading.tasks.lifecycle_coordination import (
    build_task_coordination_key,
    build_task_execution_instance_key,
)


def test_build_task_coordination_key() -> None:
    assert (
        build_task_coordination_key(
            task_name="trading.tasks.run_backtest_task",
            instance_key="task-1:execution-1",
        )
        == "task:coord:trading.tasks.run_backtest_task:task-1:execution-1"
    )


def test_build_task_execution_instance_key() -> None:
    task_id = uuid4()
    execution_id = uuid4()

    assert (
        build_task_execution_instance_key(
            task_id=task_id,
            execution_id=execution_id,
        )
        == f"{task_id}:{execution_id}"
    )
