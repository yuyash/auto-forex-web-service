"""E2E tests for /api/trading/tasks/backtest/."""

import pytest


def _create_backtest(client, config_id, name):
    """Helper: create a backtest task and return its ID."""
    resp = client.post(
        "/api/trading/tasks/backtest/",
        {
            "name": name,
            "config": str(config_id),
            "instrument": "USD_JPY",
            "start_time": "2026-01-02T00:00:00Z",
            "end_time": "2026-01-02T21:59:58Z",
            "initial_balance": "10000.00",
            "data_source": "postgresql",
        },
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data
    # Create serializer may not return id; fetch from list
    list_resp = client.get("/api/trading/tasks/backtest/", {"search": name})
    assert list_resp.status_code == 200
    results = list_resp.data.get("results", list_resp.data)
    task = next(t for t in results if t["name"] == name)
    return task["id"]


@pytest.mark.django_db
class TestBacktestTasks:
    # ── Basic CRUD ────────────────────────────────────────────────────────

    def test_list_backtest_tasks(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/tasks/backtest/")
        assert resp.status_code == 200

    def test_create_backtest_task(self, authenticated_client, strategy_config):
        _create_backtest(authenticated_client, strategy_config.id, "E2E Backtest")

    def test_get_backtest_detail(self, authenticated_client, strategy_config):
        task_id = _create_backtest(authenticated_client, strategy_config.id, "E2E Backtest Detail")
        resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == task_id

    def test_delete_backtest_task(self, authenticated_client, strategy_config):
        task_id = _create_backtest(authenticated_client, strategy_config.id, "E2E Backtest Delete")
        resp = authenticated_client.delete(f"/api/trading/tasks/backtest/{task_id}/")
        assert resp.status_code in (200, 204)

    # ── Pagination ────────────────────────────────────────────────────────

    def test_list_pagination(self, authenticated_client, strategy_config):
        """Create 2 tasks and verify paginated response structure."""
        _create_backtest(authenticated_client, strategy_config.id, "BT Pagination 1")
        _create_backtest(authenticated_client, strategy_config.id, "BT Pagination 2")
        resp = authenticated_client.get("/api/trading/tasks/backtest/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 2
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data

    # ── Filtering ─────────────────────────────────────────────────────────

    def test_list_filter_by_status(self, authenticated_client, strategy_config):
        """Verify status filter returns only matching tasks."""
        _create_backtest(authenticated_client, strategy_config.id, "BT Filter Status")
        resp = authenticated_client.get("/api/trading/tasks/backtest/", {"status": "created"})
        assert resp.status_code == 200
        assert all(t["status"] == "created" for t in resp.data["results"])

    def test_list_search(self, authenticated_client, strategy_config):
        """Verify search filter finds tasks by name."""
        _create_backtest(authenticated_client, strategy_config.id, "UniqueBacktestSearchName789")
        resp = authenticated_client.get(
            "/api/trading/tasks/backtest/", {"search": "UniqueBacktestSearchName789"}
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    # ── Start + verify sub-resources ──────────────────────────────────────

    def test_start_and_verify_sub_resources(self, authenticated_client, strategy_config):
        """Start a backtest, wait for completion, verify sub-resources have data."""
        task_id = _create_backtest(authenticated_client, strategy_config.id, "BT Execute SubRes")

        # Start (runs synchronously in eager mode)
        resp = authenticated_client.post(f"/api/trading/tasks/backtest/{task_id}/start/")
        assert resp.status_code == 200

        # Check task completed
        detail = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/")
        assert detail.status_code == 200
        assert detail.data["status"] in ("completed", "stopped", "failed")

        # ── Logs ──────────────────────────────────────────────────────────
        logs_resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/logs/")
        assert logs_resp.status_code == 200
        assert logs_resp.data["count"] > 0
        log_item = logs_resp.data["results"][0]
        assert "level" in log_item
        assert "message" in log_item
        assert "timestamp" in log_item

        # ── Summary ───────────────────────────────────────────────────────
        summary = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/summary/")
        assert summary.status_code == 200
        assert "task" in summary.data
        assert "pnl" in summary.data
        assert "counts" in summary.data

        # ── Executions ────────────────────────────────────────────────────
        exec_resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/executions/")
        assert exec_resp.status_code == 200
        assert exec_resp.data["count"] > 0

        # ── Events ────────────────────────────────────────────────────────
        events_resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/events/")
        assert events_resp.status_code == 200

        # ── Metrics ───────────────────────────────────────────────────────
        metrics_resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/metrics/")
        assert metrics_resp.status_code == 200
        assert "metrics" in metrics_resp.data

        # ── Sub-resource pagination ───────────────────────────────────────
        logs_page = authenticated_client.get(
            f"/api/trading/tasks/backtest/{task_id}/logs/", {"page_size": 1}
        )
        assert logs_page.status_code == 200
        assert len(logs_page.data["results"]) <= 1
        if logs_page.data["count"] > 1:
            assert logs_page.data["next"] is not None

        # ── Sub-resource filtering ────────────────────────────────────────
        logs_filtered = authenticated_client.get(
            f"/api/trading/tasks/backtest/{task_id}/logs/", {"level": "INFO"}
        )
        assert logs_filtered.status_code == 200

    # ── Remaining sub-resource endpoints (no execution needed) ────────────

    def test_sub_resources_accessible(self, authenticated_client, strategy_config):
        """Verify all sub-resource endpoints return 200 on a non-started task."""
        task_id = _create_backtest(
            authenticated_client, strategy_config.id, "E2E Backtest SubRes Access"
        )
        for endpoint in (
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
            resp = authenticated_client.get(f"/api/trading/tasks/backtest/{task_id}/{endpoint}/")
            assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"

    # ── Auth ──────────────────────────────────────────────────────────────

    def test_backtest_tasks_unauthenticated(self, api_client):
        resp = api_client.get("/api/trading/tasks/backtest/")
        assert resp.status_code == 401
