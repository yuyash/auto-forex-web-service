"""Integration tests for strategy configuration APIs."""

from __future__ import annotations

from datetime import timedelta

import pytest
import requests
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import StrategyConfig, TradingTask


@pytest.mark.django_db(transaction=True)
class TestStrategyConfigsApi:
    def test_list_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/strategy-configs/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_create_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/strategy-configs/"
        payload = {
            "name": "cfg1",
            "strategy_type": "floor",
            "parameters": {"instrument": "EUR_USD"},
            "description": "test",
        }
        resp = requests.post(url, json=payload, timeout=10)
        assert resp.status_code in {401, 403}

    def test_list_empty(self, live_server, auth_headers):
        url = f"{live_server.url}/api/trading/strategy-configs/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) >= {"count", "next", "previous", "results"}
        assert data["count"] == 0
        assert data["results"] == []

    def test_create_get_update_delete(self, live_server, auth_headers):
        base_url = f"{live_server.url}/api/trading/strategy-configs/"
        payload = {
            "name": "floor-cfg",
            "strategy_type": "floor",
            "parameters": {"instrument": "EUR_USD"},
            "description": "initial",
        }
        create = requests.post(base_url, headers=auth_headers, json=payload, timeout=10)
        assert create.status_code == 201
        created = create.json()
        config_id = created["id"]

        detail_url = f"{live_server.url}/api/trading/strategy-configs/{config_id}/"
        get_resp = requests.get(detail_url, headers=auth_headers, timeout=10)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "floor-cfg"

        update_payload = {
            "description": "updated",
        }
        put_resp = requests.put(detail_url, headers=auth_headers, json=update_payload, timeout=10)
        assert put_resp.status_code == 200
        assert put_resp.json()["description"] == "updated"

        del_resp = requests.delete(detail_url, headers=auth_headers, timeout=10)
        assert del_resp.status_code == 204

        missing = requests.get(detail_url, headers=auth_headers, timeout=10)
        assert missing.status_code == 404

    def test_delete_in_use_returns_409(self, live_server, auth_headers, test_user, oanda_account):
        # Create config + a RUNNING trading task referencing it
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-in-use",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-running",
            description="",
            status=TaskStatus.RUNNING,
        )

        url = f"{live_server.url}/api/trading/strategy-configs/{config.id}/"  # type: ignore[attr-defined]
        resp = requests.delete(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
class TestBacktestTaskCreateValidationApi:
    def test_backtest_create_rejects_future_end_time(self, live_server, auth_headers, test_user):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-backtest",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )

        url = f"{live_server.url}/api/trading/backtest-tasks/"
        now = timezone.now()
        payload = {
            "config": config.id,  # type: ignore[attr-defined]
            "name": "bt1",
            "description": "",
            "data_source": "postgresql",
            "start_time": (now - timedelta(days=2)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
        }

        resp = requests.post(url, headers=auth_headers, json=payload, timeout=10)
        assert resp.status_code == 400
        data = resp.json()
        assert "end_time" in data
