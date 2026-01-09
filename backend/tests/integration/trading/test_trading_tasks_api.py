"""Integration tests for trading task list/detail APIs."""

from __future__ import annotations

import pytest
import requests

from apps.trading.enums import TaskStatus
from apps.trading.models import StrategyConfig, TradingTask


@pytest.mark.django_db(transaction=True)
class TestTradingTasksApi:
    def test_list_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/trading-tasks/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_create_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/trading-tasks/"
        resp = requests.post(url, json={}, timeout=10)
        assert resp.status_code in {401, 403}

    def test_create_and_list(self, live_server, auth_headers, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-task",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )

        url = f"{live_server.url}/api/trading/trading-tasks/"
        payload = {
            "config": config.id,  # type: ignore[attr-defined]
            "oanda_account": oanda_account.id,
            "name": "task1",
            "description": "d1",
            "sell_on_stop": False,
        }
        create = requests.post(url, headers=auth_headers, json=payload, timeout=10)
        assert create.status_code == 201

        # List returns summary serializer with id
        list_resp = requests.get(url, headers=auth_headers, timeout=10)
        assert list_resp.status_code == 200
        data = list_resp.json()

        # DRF pagination may be enabled; accept either paginated or raw list
        if isinstance(data, dict) and "results" in data:
            items = data["results"]
        else:
            items = data

        assert any(item.get("name") == "task1" for item in items)

    def test_detail_patch_delete(self, live_server, auth_headers, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-detail",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-detail",
            description="old",
            status=TaskStatus.CREATED,
        )

        detail_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/"  # type: ignore[attr-defined]
        get_resp = requests.get(detail_url, headers=auth_headers, timeout=10)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "task-detail"

        patch_resp = requests.patch(
            detail_url,
            headers=auth_headers,
            json={"description": "new"},
            timeout=10,
        )
        assert patch_resp.status_code == 200

        del_resp = requests.delete(detail_url, headers=auth_headers, timeout=10)
        assert del_resp.status_code == 204

    def test_cannot_delete_running_task(self, live_server, auth_headers, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-running",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-running",
            description="",
            status=TaskStatus.RUNNING,
        )

        detail_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/"  # type: ignore[attr-defined]
        del_resp = requests.delete(detail_url, headers=auth_headers, timeout=10)
        assert del_resp.status_code == 400
