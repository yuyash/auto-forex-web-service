"""Query-count regression tests for task list APIs."""

from __future__ import annotations

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.trading.views.backtest import BacktestTaskViewSet
from apps.trading.views.trading import TradingTaskViewSet
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_backtest_task_list_query_count_is_constant(django_assert_num_queries):
    user = UserFactory()
    config = StrategyConfigurationFactory(user=user)
    for _ in range(8):
        BacktestTaskFactory(user=user, config=config)

    request = APIRequestFactory().get("/api/trading/tasks/backtest/", {"page_size": 8})
    force_authenticate(request, user=user)
    view = BacktestTaskViewSet.as_view({"get": "list"})

    with django_assert_num_queries(2):
        response = view(request)

    assert response.status_code == 200
    assert response.data["count"] == 8
    assert len(response.data["results"]) == 8


@pytest.mark.django_db
def test_trading_task_list_query_count_is_constant(django_assert_num_queries):
    user = UserFactory()
    config = StrategyConfigurationFactory(user=user)
    account = OandaAccountFactory(user=user)
    for _ in range(8):
        TradingTaskFactory(user=user, config=config, oanda_account=account)

    request = APIRequestFactory().get("/api/trading/tasks/trading/", {"page_size": 8})
    force_authenticate(request, user=user)
    view = TradingTaskViewSet.as_view({"get": "list"})

    with django_assert_num_queries(2):
        response = view(request)

    assert response.status_code == 200
    assert response.data["count"] == 8
    assert len(response.data["results"]) == 8
