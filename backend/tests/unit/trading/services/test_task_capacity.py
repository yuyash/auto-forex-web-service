"""Unit tests for task admission capacity checks."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus
from apps.trading.models import BacktestTask, TradingTask
from apps.trading.services.task_capacity import TaskCapacityService


def test_backtest_capacity_blocks_when_execution_queue_is_full(settings) -> None:
    settings.CELERY_BACKTEST_WORKER_CONCURRENCY = 1
    settings.CELERY_BACKTEST_PUBLISHER_CONCURRENCY = 2

    with (
        patch(
            "apps.trading.services.task_capacity.BacktestTask.objects.filter"
        ) as mock_backtest_filter,
        patch.object(TaskCapacityService, "_queue_usage", return_value=None),
        patch(
            "apps.trading.services.task_capacity.MarketCeleryTaskStatus.objects.filter"
        ) as mock_market_filter,
    ):
        mock_backtest_filter.return_value.count.return_value = 1
        publisher_qs = MagicMock()
        publisher_qs.count.return_value = 0
        mock_market_filter.return_value = publisher_qs

        decision = TaskCapacityService().get_task_admission(BacktestTask())

    assert decision.allowed is False
    assert "backtest" in decision.reason


def test_trading_capacity_counts_new_market_publisher_and_subscriber(settings) -> None:
    settings.CELERY_TRADING_WORKER_CONCURRENCY = 2
    settings.CELERY_MARKET_WORKER_CONCURRENCY = 1

    task = MagicMock(spec=TradingTask)
    task.oanda_account_id = 42

    with (
        patch(
            "apps.trading.services.task_capacity.TradingTask.objects.filter"
        ) as mock_trading_filter,
        patch.object(TaskCapacityService, "_queue_usage", return_value=None),
        patch.object(TaskCapacityService, "_fresh_market_tasks") as mock_fresh_market_tasks,
    ):
        mock_trading_filter.return_value.count.return_value = 0

        active_publishers = MagicMock()
        active_publishers.count.return_value = 0
        subscriber_qs = MagicMock()
        subscriber_qs.exists.return_value = False
        account_qs = MagicMock()
        account_qs.filter.return_value.exists.return_value = False
        account_qs.exists.return_value = False
        mock_fresh_market_tasks.side_effect = [active_publishers, subscriber_qs, account_qs]

        decision = TaskCapacityService().get_task_admission(task)

    assert decision.allowed is False
    assert "market" in decision.reason


@pytest.mark.django_db
def test_trading_capacity_ignores_stale_market_publishers(settings) -> None:
    settings.CELERY_TRADING_WORKER_CONCURRENCY = 2
    settings.CELERY_MARKET_WORKER_CONCURRENCY = 2
    settings.CELERY_MARKET_TASK_STALE_AFTER_SECONDS = 90

    stale_at = timezone.now() - timedelta(minutes=10)
    MarketCeleryTaskStatus.objects.create(
        task_name="market.tasks.publish_oanda_ticks",
        instance_key="2",
        status=MarketCeleryTaskStatus.Status.RUNNING,
        last_heartbeat_at=stale_at,
    )
    MarketCeleryTaskStatus.objects.create(
        task_name="market.tasks.subscribe_ticks_to_db",
        instance_key="default",
        status=MarketCeleryTaskStatus.Status.RUNNING,
        last_heartbeat_at=timezone.now(),
    )

    task = MagicMock(spec=TradingTask)
    task.oanda_account_id = 42

    with (
        patch(
            "apps.trading.services.task_capacity.TradingTask.objects.filter"
        ) as mock_trading_filter,
        patch.object(TaskCapacityService, "_queue_usage", return_value=None),
    ):
        mock_trading_filter.return_value.count.return_value = 0
        decision = TaskCapacityService().get_task_admission(task)

    assert decision.allowed is True


@pytest.mark.django_db
def test_backtest_capacity_ignores_stale_publishers(settings) -> None:
    settings.CELERY_BACKTEST_WORKER_CONCURRENCY = 2
    settings.CELERY_BACKTEST_PUBLISHER_CONCURRENCY = 2
    settings.CELERY_MARKET_TASK_STALE_AFTER_SECONDS = 90

    MarketCeleryTaskStatus.objects.create(
        task_name="market.tasks.publish_ticks_for_backtest",
        instance_key="stale",
        status=MarketCeleryTaskStatus.Status.STOPPING,
        last_heartbeat_at=timezone.now() - timedelta(minutes=10),
    )

    with (
        patch(
            "apps.trading.services.task_capacity.BacktestTask.objects.filter"
        ) as mock_backtest_filter,
        patch.object(TaskCapacityService, "_queue_usage", return_value=None),
    ):
        mock_backtest_filter.return_value.count.return_value = 0
        decision = TaskCapacityService().get_task_admission(BacktestTask())

    assert decision.allowed is True


def test_queue_usage_counts_only_active_tasks_for_dedicated_queue() -> None:
    inspector = MagicMock()
    inspector.active_queues.return_value = {
        "worker-market@host": [{"name": "market"}],
        "worker-trading@host": [{"name": "trading"}],
    }
    inspector.active.return_value = {
        "worker-market@host": [{"name": "market.tasks.subscribe_ticks_to_db"}],
        "worker-trading@host": [{"name": "trading.tasks.run_trading_task"}],
    }
    inspector.reserved.return_value = {
        "worker-market@host": [{"name": "market.tasks.publish_oanda_ticks"}],
        "worker-trading@host": [],
    }

    with patch("apps.trading.services.task_capacity.current_app.control.inspect") as mock_inspect:
        mock_inspect.return_value = inspector
        assert TaskCapacityService()._queue_usage("market") == 1
