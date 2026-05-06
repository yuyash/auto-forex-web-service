"""Integration tests for task event stream snapshots."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTask, ExecutionState, TradingTask
from apps.trading.views.stream import TaskEventStreamView
from tests.integration.factories import BacktestTaskFactory, TradingTaskFactory


@pytest.mark.django_db
def test_trading_snapshot_fetch_does_not_require_progress_model_field():
    task = TradingTaskFactory(status=TaskStatus.CREATED)

    payload = TaskEventStreamView._fetch_snapshot_sync(
        task_model=TradingTask,
        task_id=task.pk,
        user_id=task.user_id,
        task_type=TaskType.TRADING.value,
    )

    assert payload is not None
    assert payload["id"] == str(task.pk)
    assert payload["status"] == TaskStatus.CREATED
    assert payload["progress"] == 0


@pytest.mark.django_db
def test_backtest_snapshot_fetch_computes_progress_from_execution_state():
    start_time = timezone.now()
    execution_id = uuid4()
    task = BacktestTaskFactory(
        status=TaskStatus.RUNNING,
        start_time=start_time,
        end_time=start_time + timedelta(hours=2),
        execution_id=execution_id,
    )
    ExecutionState.objects.create(
        task_type=TaskType.BACKTEST.value,
        task_id=task.pk,
        execution_id=execution_id,
        current_balance=Decimal("10000"),
        last_tick_timestamp=start_time + timedelta(hours=1),
    )

    payload = TaskEventStreamView._fetch_snapshot_sync(
        task_model=BacktestTask,
        task_id=task.pk,
        user_id=task.user_id,
        task_type=TaskType.BACKTEST.value,
    )

    assert payload is not None
    assert payload["id"] == str(task.pk)
    assert payload["status"] == TaskStatus.RUNNING
    assert payload["progress"] == 50
