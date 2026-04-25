"""Tests for centralized task policy decisions."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.services.task_policy import action_policy_for_task, validate_task_update_fields
from tests.integration.factories import BacktestTaskFactory, TradingTaskFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.CREATED, {"can_start": True, "can_delete": True}),
        (TaskStatus.RUNNING, {"can_stop": True, "can_pause": True}),
        (TaskStatus.PAUSED, {"can_stop": True, "can_resume": True}),
        (TaskStatus.STOPPED, {"can_resume": True, "can_restart": True, "can_delete": True}),
        (TaskStatus.COMPLETED, {"can_restart": True, "can_delete": True}),
        (TaskStatus.FAILED, {"can_restart": True, "can_delete": True}),
    ],
)
def test_backtest_action_policy_matrix(status: TaskStatus, expected: dict[str, bool]) -> None:
    task = BacktestTaskFactory(status=status, execution_id=uuid4())

    policy = action_policy_for_task(task, task_type="backtest").as_dict()

    for field, value in expected.items():
        assert policy[field] is value


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.CREATED, {"can_start": True, "can_delete": True}),
        (TaskStatus.RUNNING, {"can_stop": True, "can_pause": False}),
        (TaskStatus.STOPPED, {"can_resume": True, "can_restart": True, "can_delete": True}),
        (TaskStatus.FAILED, {"can_resume": True, "can_restart": True, "can_delete": True}),
    ],
)
def test_trading_action_policy_matrix(status: TaskStatus, expected: dict[str, bool]) -> None:
    task = TradingTaskFactory(status=status, execution_id=uuid4())

    policy = action_policy_for_task(task, task_type="trading").as_dict()

    for field, value in expected.items():
        assert policy[field] is value


@pytest.mark.django_db
def test_update_policy_allows_paused_backtest_execution_settings() -> None:
    task = BacktestTaskFactory(status=TaskStatus.PAUSED, execution_id=uuid4())

    validate_task_update_fields(
        task=task,
        changed_fields={"name", "description"},
        task_type="backtest",
    )
    validate_task_update_fields(
        task=task,
        changed_fields={"config"},
        task_type="backtest",
    )

    running_task = BacktestTaskFactory(status=TaskStatus.RUNNING, execution_id=uuid4())
    with pytest.raises(ValueError, match="actively running"):
        validate_task_update_fields(
            task=running_task,
            changed_fields={"config"},
            task_type="backtest",
        )
