"""Unit tests for lifecycle write helpers."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.tasks.lifecycle_writes import TaskLifecycleWriter


def test_persist_state_if_current_updates_only_matching_status() -> None:
    class TaskModel:
        objects = MagicMock()

    task = TaskModel()
    task.pk = uuid4()
    task.status = TaskStatus.RUNNING
    TaskModel.objects.filter.return_value.update.return_value = 1

    writer = TaskLifecycleWriter(logger=MagicMock())
    writer.persist_state_if_current(
        command="stop",
        task=task,
        from_status=TaskStatus.RUNNING,
        to_status=TaskStatus.STOPPING,
        extra_updates={"sell_on_stop": True},
    )

    TaskModel.objects.filter.assert_called_once_with(
        pk=task.pk,
        status=TaskStatus.RUNNING,
    )
    update_kwargs = TaskModel.objects.filter.return_value.update.call_args.kwargs
    assert update_kwargs["status"] == TaskStatus.STOPPING
    assert update_kwargs["sell_on_stop"] is True
    assert "updated_at" in update_kwargs
    assert task.status == TaskStatus.STOPPING
    assert task.sell_on_stop is True


def test_update_if_current_raises_conflict_when_status_changed() -> None:
    from apps.trading.tasks.service import TaskConflictError

    class TaskModel:
        objects = MagicMock()

    task = TaskModel()
    task.pk = uuid4()
    task.status = TaskStatus.RUNNING
    task.refresh_from_db = MagicMock()
    TaskModel.objects.filter.return_value.update.return_value = 0

    writer = TaskLifecycleWriter(logger=MagicMock())
    with pytest.raises(TaskConflictError, match="superseded"):
        writer.update_if_current(
            command="pause",
            task=task,
            expected_status=TaskStatus.RUNNING,
            updates={"status": TaskStatus.PAUSED},
        )

    TaskModel.objects.filter.assert_called_once_with(
        pk=task.pk,
        status=TaskStatus.RUNNING,
    )
    task.refresh_from_db.assert_called_once()


def test_persist_terminal_state_if_current_sets_completed_at() -> None:
    class TaskModel:
        objects = MagicMock()

    task = TaskModel()
    task.pk = uuid4()
    task.status = TaskStatus.RUNNING
    TaskModel.objects.filter.return_value.update.return_value = 1

    writer = TaskLifecycleWriter(logger=MagicMock())
    writer.persist_terminal_state_if_current(
        command="cancel",
        task=task,
        from_status=TaskStatus.RUNNING,
        to_status=TaskStatus.STOPPED,
    )

    update_kwargs = TaskModel.objects.filter.return_value.update.call_args.kwargs
    assert update_kwargs["status"] == TaskStatus.STOPPED
    assert "completed_at" in update_kwargs
    assert task.status == TaskStatus.STOPPED
    assert task.completed_at == update_kwargs["completed_at"]


def test_update_if_current_saves_detached_task() -> None:
    class DetachedTask:
        pass

    task = DetachedTask()
    task.pk = uuid4()
    task.status = TaskStatus.RUNNING
    task.save = MagicMock()

    writer = TaskLifecycleWriter(logger=MagicMock())
    writer.update_if_current(
        command="pause",
        task=task,
        expected_status=TaskStatus.RUNNING,
        updates={"status": TaskStatus.PAUSED},
    )

    assert task.status == TaskStatus.PAUSED
    task.save.assert_called_once()
