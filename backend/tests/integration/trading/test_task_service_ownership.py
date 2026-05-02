"""Ownership checks for task lifecycle service entry points."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.tasks.service import TaskService, TaskValidationError
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_start_task_rejects_mismatched_user() -> None:
    owner = UserFactory()
    intruder = UserFactory()
    config = StrategyConfigurationFactory(user=owner)
    task = BacktestTaskFactory(user=owner, config=config)

    with pytest.raises(TaskValidationError, match="not accessible"):
        TaskService().start_task(task, user=intruder)

    task.refresh_from_db()
    assert task.status == TaskStatus.CREATED
    assert task.execution_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method_name", "status"),
    [
        ("stop_task", TaskStatus.RUNNING),
        ("pause_task", TaskStatus.RUNNING),
        ("cancel_task", TaskStatus.RUNNING),
        ("restart_task", TaskStatus.STOPPED),
        ("resume_task", TaskStatus.PAUSED),
    ],
)
def test_backtest_task_id_lifecycle_methods_reject_unowned_task(
    method_name: str,
    status: TaskStatus,
) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    config = StrategyConfigurationFactory(user=owner)
    task = BacktestTaskFactory(
        user=owner,
        config=config,
        status=status,
        execution_id=uuid4(),
    )

    with pytest.raises(TaskValidationError, match="not accessible"):
        getattr(TaskService(), method_name)(task.pk, user=intruder)

    task.refresh_from_db()
    assert task.status == status


@pytest.mark.django_db
def test_trading_task_id_lifecycle_methods_reject_unowned_task() -> None:
    owner = UserFactory()
    intruder = UserFactory()
    config = StrategyConfigurationFactory(user=owner)
    account = OandaAccountFactory(user=owner)
    task = TradingTaskFactory(
        user=owner,
        config=config,
        oanda_account=account,
        status=TaskStatus.RUNNING,
        execution_id=uuid4(),
    )

    with pytest.raises(TaskValidationError, match="not accessible"):
        TaskService().stop_task(task.pk, user=intruder)

    task.refresh_from_db()
    assert task.status == TaskStatus.RUNNING
