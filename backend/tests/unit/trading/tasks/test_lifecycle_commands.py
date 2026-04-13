"""Unit tests for lifecycle command adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.trading.enums import StopMode, TaskStatus
from apps.trading.tasks.lifecycle_commands import (
    LifecycleCommandAdapters,
    TaskLifecycleCommands,
)


def _make_commands(service: MagicMock) -> tuple[TaskLifecycleCommands, MagicMock]:
    logger = MagicMock()
    events = MagicMock()
    adapters = LifecycleCommandAdapters(
        inspect_workers=MagicMock(return_value={"worker1": {}}),
        signal_stop=MagicMock(),
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
    task = MagicMock(pk=task_id, status=TaskStatus.RUNNING, execution_id=execution_id)
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "trading")

    commands, adapters = _make_commands(service)

    result = commands.stop(task_id, "immediate")

    assert result is True
    adapters.signal_stop.assert_called_once()
    adapters.revoke_execution.assert_called_once_with(execution_id)
    adapters.dispatch_stop.assert_called_once_with(task_id, False, StopMode.IMMEDIATE)


def test_restart_uses_injected_sleep() -> None:
    task_id = uuid4()
    execution_id = uuid4()
    task_model = type("DummyTaskModel", (), {"objects": MagicMock()})
    task = task_model()
    task.pk = task_id
    task.status = TaskStatus.RUNNING
    task.execution_id = execution_id
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
    task = MagicMock(pk=task_id, status=TaskStatus.RUNNING, execution_id=uuid4())
    service = MagicMock()
    service._get_task_and_type.return_value = (task, "backtest")

    commands, adapters = _make_commands(service)
    adapters.signal_stop.side_effect = RuntimeError("redis unavailable")

    result = commands.stop(task_id, "graceful")

    assert result is True
    adapters.dispatch_stop.assert_called_once()


@patch("apps.market.tasks.ensure_tick_pubsub_running.apply_async")
def test_start_trading_task_kicks_market_supervisor(mock_apply_async) -> None:
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
