"""Integration tests for backtest task list/detail APIs."""

from __future__ import annotations

from datetime import timedelta

import pytest
import requests
from django.utils import timezone

from apps.trading.models import BacktestTask, StrategyConfig


@pytest.mark.django_db(transaction=True)
class TestBacktestTasksApi:
    def test_list_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/backtest-tasks/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_create_and_detail_and_delete(self, live_server, auth_headers, test_user):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-bt",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )

        url = f"{live_server.url}/api/trading/backtest-tasks/"
        now = timezone.now()
        payload = {
            "config": config.id,  # type: ignore[attr-defined]
            "name": "bt-task",
            "description": "",
            "data_source": "postgresql",
            "start_time": (now - timedelta(days=3)).isoformat(),
            "end_time": (now - timedelta(days=2)).isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
        }

        create = requests.post(url, headers=auth_headers, json=payload, timeout=10)
        assert create.status_code == 201
        task = BacktestTask.objects.get(user=test_user, name="bt-task")
        task_id = task.id  # type: ignore[attr-defined]

        detail = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task_id}/",
            headers=auth_headers,
            timeout=10,
        )
        assert detail.status_code == 200
        assert detail.json()["name"] == "bt-task"

        delete = requests.delete(
            f"{live_server.url}/api/trading/backtest-tasks/{task_id}/",
            headers=auth_headers,
            timeout=10,
        )
        assert delete.status_code == 204

        assert not BacktestTask.objects.filter(id=task_id).exists()
