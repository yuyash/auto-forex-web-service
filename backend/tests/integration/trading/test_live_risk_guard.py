"""Integration coverage for start-time live-trading guardrails."""

from __future__ import annotations

import pytest

from apps.market.enums import ApiType
from apps.trading.enums import TaskStatus
from apps.trading.tasks.service import TaskService, TaskValidationError
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_start_blocks_live_account_before_worker_ownership(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False
    user = UserFactory()
    account = OandaAccountFactory(user=user, api_type=ApiType.LIVE)
    config = StrategyConfigurationFactory(user=user)
    task = TradingTaskFactory(
        user=user,
        oanda_account=account,
        config=config,
        dry_run=False,
        status=TaskStatus.CREATED,
    )

    with pytest.raises(TaskValidationError, match="Live OANDA accounts are disabled"):
        TaskService().start_task(task, user=user)

    task.refresh_from_db()
    assert task.status == TaskStatus.CREATED
    assert task.execution_id is None
    assert task.celery_task_id is None
