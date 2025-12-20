"""Integration tests for trading task action APIs."""

from __future__ import annotations

import pytest
import requests

from apps.trading.enums import TaskStatus
from apps.trading.models import StrategyConfig, TradingTask


@pytest.mark.django_db(transaction=True)
class TestTradingTaskActionsApi:
    def test_actions_require_auth(self, live_server, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-auth",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-auth",
            description="",
            status=TaskStatus.CREATED,
        )

        for suffix in [
            "start/",
            "stop/",
            "pause/",
            "resume/",
            "restart/",
            "status/",
            "executions/",
            "logs/",
            "results/",
            "copy/",
        ]:
            url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/{suffix}"
            if suffix in {"status/", "executions/", "logs/", "results/"}:
                resp = requests.get(url, timeout=10)
            else:
                resp = requests.post(url, json={}, timeout=10)
            assert resp.status_code in {401, 403}

    def test_lifecycle_happy_path(self, live_server, auth_headers, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-life",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-life",
            description="",
            status=TaskStatus.CREATED,
        )

        start_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/start/"
        start = requests.post(start_url, headers=auth_headers, json={}, timeout=10)
        assert start.status_code == 202

        pause_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/pause/"
        pause = requests.post(pause_url, headers=auth_headers, json={}, timeout=10)
        assert pause.status_code == 200

        resume_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/resume/"
        resume = requests.post(resume_url, headers=auth_headers, json={}, timeout=10)
        assert resume.status_code == 200

        stop_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/stop/"
        stop = requests.post(stop_url, headers=auth_headers, json={"mode": "graceful"}, timeout=10)
        assert stop.status_code == 200

        restart_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/restart/"
        restart = requests.post(
            restart_url, headers=auth_headers, json={"clear_state": True}, timeout=10
        )
        assert restart.status_code == 202

        status_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/status/"
        status_resp = requests.get(status_url, headers=auth_headers, timeout=10)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["task_id"] == task.id
        assert status_data["task_type"] == "trading"
        assert "status" in status_data
        assert "progress" in status_data

        executions_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/executions/"
        exec_resp = requests.get(executions_url, headers=auth_headers, timeout=10)
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert set(exec_data.keys()) >= {"count", "results"}

        logs_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/logs/?limit=10&offset=0"
        logs_resp = requests.get(logs_url, headers=auth_headers, timeout=10)
        assert logs_resp.status_code == 200
        logs_data = logs_resp.json()
        assert set(logs_data.keys()) >= {"count", "next", "previous", "results"}

        results_url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/results/"
        results_resp = requests.get(results_url, headers=auth_headers, timeout=10)
        assert results_resp.status_code == 200
        results_data = results_resp.json()
        assert results_data["task_id"] == task.id
        assert results_data["task_type"] == "trading"
        assert "has_live" in results_data
        assert "has_metrics" in results_data

    def test_copy_requires_new_name(self, live_server, auth_headers, test_user, oanda_account):
        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-copy",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="task-copy",
            description="",
            status=TaskStatus.CREATED,
        )

        url = f"{live_server.url}/api/trading/trading-tasks/{task.id}/copy/"
        resp = requests.post(url, headers=auth_headers, json={}, timeout=10)
        assert resp.status_code == 400
