"""Integration tests for backtest task action APIs."""

from __future__ import annotations

from datetime import timedelta

import pytest
import requests
from django.utils import timezone

from apps.trading.models import BacktestTask, StrategyConfig


@pytest.mark.django_db(transaction=True)
class TestBacktestTaskActionsApi:
    def _create_backtest_task(self, *, user):
        config = StrategyConfig.objects.create(
            user=user,
            name="cfg-bt-actions",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        now = timezone.now()
        return BacktestTask.objects.create(
            user=user,
            config=config,
            name="bt-actions",
            description="",
            data_source="postgresql",
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=2),
        )

    def test_actions_require_auth(self, live_server, test_user):
        task = self._create_backtest_task(user=test_user)

        for suffix in [
            "start/",
            "stop/",
            "status/",
            "executions/",
            "logs/",
            "export/",
            "results/",
            "copy/",
        ]:
            url = f"{live_server.url}/api/trading/backtest-tasks/{task.id}/{suffix}"
            if suffix in {"status/", "executions/", "logs/", "export/", "results/"}:
                resp = requests.get(url, timeout=10)
            else:
                resp = requests.post(url, json={}, timeout=10)
            assert resp.status_code in {401, 403}

    def test_start_stop_status_logs_live_results_and_export_404(
        self, live_server, auth_headers, test_user
    ):
        task = self._create_backtest_task(user=test_user)

        start = requests.post(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/start/",
            headers=auth_headers,
            json={},
            timeout=10,
        )
        assert start.status_code == 202

        status_resp = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/status/",
            headers=auth_headers,
            timeout=10,
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["task_id"] == task.id
        assert status_data["task_type"] == "backtest"

        executions = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/executions/",
            headers=auth_headers,
            timeout=10,
        )
        assert executions.status_code == 200
        assert set(executions.json().keys()) >= {"count", "results"}

        logs = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/logs/?limit=10&offset=0",
            headers=auth_headers,
            timeout=10,
        )
        assert logs.status_code == 200
        assert set(logs.json().keys()) >= {"count", "next", "previous", "results"}

        results = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/results/",
            headers=auth_headers,
            timeout=10,
        )
        assert results.status_code == 200
        results_data = results.json()
        assert results_data["task_id"] == task.id
        assert results_data["task_type"] == "backtest"
        assert "has_live" in results_data
        assert "has_metrics" in results_data

        export = requests.get(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/export/",
            headers=auth_headers,
            timeout=10,
        )
        assert export.status_code == 404

        stop = requests.post(
            f"{live_server.url}/api/trading/backtest-tasks/{task.id}/stop/",
            headers=auth_headers,
            json={},
            timeout=10,
        )
        # Can be 200 (if RUNNING) or 400 if start hasn't flipped status yet
        assert stop.status_code in {200, 400}
