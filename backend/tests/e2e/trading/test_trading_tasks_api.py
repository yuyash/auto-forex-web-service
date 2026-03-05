"""E2E tests for /api/trading/tasks/trading/."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.e2e.helpers import CsvTickDataSource

TICK_CSV = Path(__file__).parent.parent / "fixtures" / "tick_data_usd_jpy.csv"


def _create_task(client, config_id, account_id, name, dry_run=True):
    """Helper: create a trading task and return its ID."""
    resp = client.post(
        "/api/trading/tasks/trading/",
        {
            "name": name,
            "config_id": str(config_id),
            "account_id": account_id,
            "dry_run": dry_run,
        },
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data
    # Create serializer doesn't return id; fetch from list
    list_resp = client.get("/api/trading/tasks/trading/", {"search": name})
    assert list_resp.status_code == 200
    results = list_resp.data.get("results", list_resp.data)
    task = next(t for t in results if t["name"] == name)
    return task["id"]


@pytest.mark.django_db
class TestTradingTasks:
    # ── Basic CRUD ────────────────────────────────────────────────────────

    def test_list_trading_tasks(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/tasks/trading/")
        assert resp.status_code == 200

    def test_create_trading_task(self, authenticated_client, oanda_account, strategy_config):
        resp = authenticated_client.post(
            "/api/trading/tasks/trading/",
            {
                "name": "E2E Trading Task",
                "config_id": str(strategy_config.id),
                "account_id": oanda_account.id,
                "dry_run": True,
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data

    def test_get_trading_task_detail(self, authenticated_client, oanda_account, strategy_config):
        task_id = _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "E2E Trading Detail",
        )
        resp = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == task_id

    def test_delete_trading_task(self, authenticated_client, oanda_account, strategy_config):
        task_id = _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "E2E Trading Delete",
        )
        resp = authenticated_client.delete(f"/api/trading/tasks/trading/{task_id}/")
        assert resp.status_code in (200, 204)

    # ── Pagination ────────────────────────────────────────────────────────

    def test_list_pagination(self, authenticated_client, oanda_account, strategy_config):
        """Create 2 tasks and verify paginated response structure."""
        _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "TT Pagination 1",
        )
        _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "TT Pagination 2",
        )
        resp = authenticated_client.get("/api/trading/tasks/trading/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 2
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data

    # ── Filtering ─────────────────────────────────────────────────────────

    def test_list_filter_by_status(self, authenticated_client, oanda_account, strategy_config):
        """Verify status filter returns only matching tasks."""
        _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "TT Filter Status",
        )
        resp = authenticated_client.get("/api/trading/tasks/trading/", {"status": "created"})
        assert resp.status_code == 200
        assert all(t["status"] == "created" for t in resp.data["results"])

    def test_list_search(self, authenticated_client, oanda_account, strategy_config):
        """Verify search filter finds tasks by name."""
        _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "UniqueTradingSearchName456",
        )
        resp = authenticated_client.get(
            "/api/trading/tasks/trading/", {"search": "UniqueTradingSearchName456"}
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    # ── Start dry-run + verify sub-resources ──────────────────────────────

    def test_start_dry_run_and_verify_sub_resources(
        self, authenticated_client, oanda_account, strategy_config
    ):
        """Start a dry-run trading task with CSV data, verify sub-resources."""
        task_id = _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "TT Execute SubRes",
        )

        csv_source = CsvTickDataSource(TICK_CSV, batch_size=200)
        with patch(
            "apps.trading.tasks.trading.LiveTickDataSource",
            return_value=csv_source,
        ):
            resp = authenticated_client.post(f"/api/trading/tasks/trading/{task_id}/start/")
            assert resp.status_code == 200, resp.data

        # Verify task completed/stopped
        detail = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/")
        assert detail.status_code == 200
        assert detail.data["status"] in ("completed", "stopped", "failed")

        # ── Logs ──────────────────────────────────────────────────────────
        logs = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/logs/")
        assert logs.status_code == 200
        assert logs.data["count"] > 0
        log_item = logs.data["results"][0]
        assert "level" in log_item
        assert "message" in log_item
        assert "timestamp" in log_item

        # ── Summary ───────────────────────────────────────────────────────
        summary = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/summary/")
        assert summary.status_code == 200
        assert "task" in summary.data
        assert "pnl" in summary.data

        # ── Executions ────────────────────────────────────────────────────
        execs = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/executions/")
        assert execs.status_code == 200
        assert execs.data["count"] > 0

        # ── Events ────────────────────────────────────────────────────────
        events = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/events/")
        assert events.status_code == 200

        # ── Metrics ───────────────────────────────────────────────────────
        metrics = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/metrics/")
        assert metrics.status_code == 200
        assert "metrics" in metrics.data

        # ── Sub-resource pagination ───────────────────────────────────────
        logs_page = authenticated_client.get(
            f"/api/trading/tasks/trading/{task_id}/logs/", {"page_size": 1}
        )
        assert logs_page.status_code == 200
        assert len(logs_page.data["results"]) <= 1
        if logs_page.data["count"] > 1:
            assert logs_page.data["next"] is not None

    # ── Sub-resource endpoints (no execution) ─────────────────────────────

    def test_sub_resources_accessible(self, authenticated_client, oanda_account, strategy_config):
        """Verify all sub-resource endpoints return 200 on a non-started task."""
        task_id = _create_task(
            authenticated_client,
            strategy_config.id,
            oanda_account.id,
            "E2E Trading SubRes Access",
        )
        for ep in (
            "logs",
            "events",
            "strategy-events",
            "trades",
            "positions",
            "orders",
            "summary",
            "executions",
            "metrics",
        ):
            resp = authenticated_client.get(f"/api/trading/tasks/trading/{task_id}/{ep}/")
            assert resp.status_code == 200, f"{ep} returned {resp.status_code}"

    # ── Auth ──────────────────────────────────────────────────────────────

    def test_trading_tasks_unauthenticated(self, api_client):
        resp = api_client.get("/api/trading/tasks/trading/")
        assert resp.status_code == 401
