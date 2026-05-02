"""Unit tests for lifecycle command adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.enums import StopMode, TaskStatus
from apps.trading.tasks.lifecycle_adapters import LifecycleCommandAdapters
from apps.trading.tasks.lifecycle_commands import (
    TaskLifecycleCommands,
)
from apps.trading.tasks.lifecycle_events import TaskLifecycleKind


def _make_commands(service: MagicMock) -> tuple[TaskLifecycleCommands, MagicMock]:
    logger = MagicMock()
    events = MagicMock()
    adapters = LifecycleCommandAdapters(
        inspect_workers=MagicMock(return_value={"worker1": {}}),
        signal_stop=MagicMock(),
        signal_pause=MagicMock(),
        revoke_execution=MagicMock(),
        dispatch_stop=MagicMock(),
        sleep=MagicMock(),
    )
    return (
        TaskLifecycleCommands(
            service=service,
            logger=logger,
            events=events,
            adapters=adapters,
        ),
        adapters,
    )


def test_stop_uses_injected_adapters() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    celery_task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.RUNNING,
        execution_id=execution_id,
        celery_task_id=celery_task_id,
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "trading")

    commands, adapters = _make_commands(service)

    result = commands.stop(task_id, "immediate")

    assert result is True
    adapters.signal_stop.assert_called_once()
    adapters.revoke_execution.assert_called_once_with(celery_task_id)
    adapters.dispatch_stop.assert_called_once_with(task_id, False, StopMode.IMMEDIATE)
    event = commands.events.publish_spec.call_args.kwargs["event"]
    assert event.kind == TaskLifecycleKind.STOP_REQUESTED
    assert event.extra_details == {"mode": StopMode.IMMEDIATE.value}


def test_restart_uses_injected_sleep() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    celery_task_id = uuid4()
    task_model = type("DummyTaskModel", (), {"objects": MagicMock()})
    task = task_model()
    task.pk = task_id
    task.status = TaskStatus.RUNNING
    task.execution_id = execution_id
    task.celery_task_id = celery_task_id
    task.refresh_from_db = MagicMock(
        side_effect=lambda: setattr(task, "status", TaskStatus.CREATED)
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")
    service.stop_task = MagicMock(return_value=True)
    service.start_task = MagicMock(return_value=task)
    service.writer.clear_execution_history = MagicMock()
    task_model.objects.filter.return_value.update.return_value = 1

    commands, adapters = _make_commands(service)

    result = commands.restart(task_id)

    assert result is task
    adapters.sleep.assert_called_once_with(1)


def test_stop_continues_when_signal_adapter_fails() -> None:
    task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.RUNNING,
        execution_id=uuid4(),
        celery_task_id=uuid4(),
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")

    commands, adapters = _make_commands(service)
    adapters.signal_stop.side_effect = RuntimeError("redis unavailable")

    result = commands.stop(task_id, "graceful")

    assert result is True
    adapters.dispatch_stop.assert_called_once()


def test_pause_rejects_trading_tasks() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    task = MagicMock(pk=task_id, status=TaskStatus.RUNNING, execution_id=execution_id)
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "trading")

    commands, adapters = _make_commands(service)

    with pytest.raises(ValueError, match="Pause is not supported for trading tasks"):
        commands.pause(task_id)

    adapters.signal_pause.assert_not_called()


def test_pause_uses_injected_adapter_for_backtest() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    task = MagicMock(pk=task_id, status=TaskStatus.RUNNING, execution_id=execution_id)
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")

    commands, adapters = _make_commands(service)

    result = commands.pause(task_id)

    assert result is True
    service.writer.persist_state_if_current.assert_called_once_with(
        command="pause",
        task=task,
        from_status=TaskStatus.RUNNING,
        to_status=TaskStatus.PAUSED,
    )
    adapters.signal_pause.assert_called_once()


def test_stop_rejects_created_task_state() -> None:
    task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.CREATED,
        execution_id=uuid4(),
        celery_task_id=uuid4(),
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")

    commands, adapters = _make_commands(service)

    with pytest.raises(ValueError, match="cannot be stopped from"):
        commands.stop(task_id, "graceful")

    adapters.dispatch_stop.assert_not_called()


def test_stop_rejects_stale_transition_before_side_effects() -> None:
    from apps.trading.tasks.service import TaskConflictError

    task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.RUNNING,
        execution_id=uuid4(),
        celery_task_id=uuid4(),
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "trading")
    service.writer.persist_state_if_current.side_effect = TaskConflictError("superseded")
    commands, adapters = _make_commands(service)

    with pytest.raises(TaskConflictError, match="superseded"):
        commands.stop(task_id, "graceful")

    adapters.signal_stop.assert_not_called()
    adapters.dispatch_stop.assert_not_called()
    adapters.revoke_execution.assert_not_called()


def test_pause_rejects_stale_transition_before_signal() -> None:
    from apps.trading.tasks.service import TaskConflictError

    task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.RUNNING,
        execution_id=uuid4(),
        celery_task_id=uuid4(),
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")
    service.writer.persist_state_if_current.side_effect = TaskConflictError("superseded")
    commands, adapters = _make_commands(service)

    with pytest.raises(TaskConflictError, match="superseded"):
        commands.pause(task_id)

    adapters.signal_pause.assert_not_called()


def test_cancel_rejects_stale_transition_before_revoke() -> None:
    from apps.trading.tasks.service import TaskConflictError

    task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.RUNNING,
        execution_id=uuid4(),
        celery_task_id=uuid4(),
    )
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")
    service.get_celery_result = MagicMock()
    service.writer.persist_terminal_state_if_current.side_effect = TaskConflictError("superseded")
    commands, _ = _make_commands(service)

    with pytest.raises(TaskConflictError, match="superseded"):
        commands.cancel(task_id)

    service.get_celery_result.assert_not_called()


@pytest.mark.django_db
def test_resume_emits_audit_log_payload() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    old_celery_task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.STOPPED,
        execution_id=execution_id,
        celery_task_id=old_celery_task_id,
    )
    task.save = MagicMock()
    task_model = MagicMock()
    task_model.objects.select_for_update.return_value.get.return_value = task
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")
    service._get_task_model.return_value = task_model
    service.get_celery_result.return_value = None
    service._dispatch_task = MagicMock()

    commands, _ = _make_commands(service)

    commands.resume(task_id)

    audit_calls = [
        c
        for c in commands.logger.info.call_args_list
        if c.args and isinstance(c.args[0], str) and c.args[0].startswith("[LIFECYCLE:AUDIT]")
    ]
    assert audit_calls
    payload = audit_calls[-1].args[1]
    assert payload["from_status"] == TaskStatus.STOPPED.value
    assert payload["to_status"] == TaskStatus.STARTING.value


@pytest.mark.django_db
def test_resume_allows_stopped_backtest_and_rotates_only_celery_task_id() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    old_celery_task_id = uuid4()
    task = MagicMock(
        pk=task_id,
        status=TaskStatus.STOPPED,
        execution_id=execution_id,
        celery_task_id=old_celery_task_id,
    )
    task.save = MagicMock()
    task_model = MagicMock()
    task_model.objects.select_for_update.return_value.get.return_value = task
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")
    service._get_task_model.return_value = task_model
    service.get_celery_result.return_value = None
    service._dispatch_task = MagicMock()

    commands, adapters = _make_commands(service)

    result = commands.resume(task_id)

    assert result is task
    assert task.status == TaskStatus.STARTING
    assert task.execution_id == execution_id
    assert task.celery_task_id != old_celery_task_id
    save_fields = task.save.call_args.kwargs["update_fields"]
    assert "error_message" in save_fields
    assert "error_traceback" in save_fields
    assert "completed_at" in save_fields
    adapters.revoke_execution.assert_called_once_with(old_celery_task_id)
    service._dispatch_task.assert_called_once_with(task, "backtest")
    event = commands.events.publish_spec.call_args.kwargs["event"]
    assert event.kind == TaskLifecycleKind.RESUME_REQUESTED
    assert event.description == f"Task resume requested (from {TaskStatus.STOPPED.value})"


@patch("apps.market.tasks.ensure_tick_pubsub_running.apply_async")
@pytest.mark.django_db
def test_start_trading_task_kicks_market_supervisor(mock_apply_async, settings) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = False
    task = type("TradingTaskStub", (), {})()
    task.pk = uuid4()
    task.status = TaskStatus.CREATED
    task.execution_id = uuid4()
    task.instrument = "USD_JPY"
    service = MagicMock()
    service._dispatch_task = MagicMock()
    commands, _ = _make_commands(service)
    commands._prepare_start = MagicMock(return_value=task)
    commands._log_worker_state = MagicMock()

    result = commands.start(task)

    assert result is task
    mock_apply_async.assert_called_once_with(countdown=0, queue="system")


@patch("apps.market.tasks.ensure_tick_pubsub_running.apply_async")
@pytest.mark.django_db
def test_start_trading_task_skips_market_supervisor_in_eager_mode(
    mock_apply_async, settings
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    task = type("TradingTaskStub", (), {})()
    task.pk = uuid4()
    task.status = TaskStatus.CREATED
    task.execution_id = uuid4()
    task.instrument = "USD_JPY"
    service = MagicMock()
    service._dispatch_task = MagicMock()
    commands, _ = _make_commands(service)
    commands._prepare_start = MagicMock(return_value=task)
    commands._log_worker_state = MagicMock()

    result = commands.start(task)

    assert result is task
    mock_apply_async.assert_not_called()
