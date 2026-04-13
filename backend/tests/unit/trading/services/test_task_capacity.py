"""Unit tests for task admission capacity checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.trading.models import BacktestTask, TradingTask
from apps.trading.services.task_capacity import TaskCapacityService


def test_backtest_capacity_blocks_when_execution_queue_is_full(settings) -> None:
    settings.CELERY_BACKTEST_WORKER_CONCURRENCY = 1
    settings.CELERY_BACKTEST_PUBLISHER_CONCURRENCY = 2

    with (
        patch(
            "apps.trading.services.task_capacity.BacktestTask.objects.filter"
        ) as mock_backtest_filter,
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

    task = TradingTask()
    task.oanda_account_id = 42

    with (
        patch(
            "apps.trading.services.task_capacity.TradingTask.objects.filter"
        ) as mock_trading_filter,
        patch(
            "apps.trading.services.task_capacity.MarketCeleryTaskStatus.objects.filter"
        ) as mock_market_filter,
    ):
        mock_trading_filter.return_value.count.return_value = 0

        active_publishers = MagicMock()
        active_publishers.count.return_value = 0
        subscriber_qs = MagicMock()
        subscriber_qs.exists.return_value = False
        account_qs = MagicMock()
        account_qs.exists.return_value = False
        mock_market_filter.side_effect = [active_publishers, subscriber_qs, account_qs]

        decision = TaskCapacityService().get_task_admission(task)

    assert decision.allowed is False
    assert "market" in decision.reason
