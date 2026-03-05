"""E2E tests for /api/trading/strategies/."""

import pytest


@pytest.mark.django_db
class TestStrategies:
    def test_list_strategies(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/")
        assert resp.status_code == 200

    def test_list_strategies_structure(self, authenticated_client):
        """Verify response structure contains strategies with expected fields."""
        resp = authenticated_client.get("/api/trading/strategies/")
        assert resp.status_code == 200
        assert "strategies" in resp.data
        assert "count" in resp.data
        assert resp.data["count"] > 0
        strategy = resp.data["strategies"][0]
        assert "id" in strategy
        assert "name" in strategy
        assert "config_schema" in strategy

    def test_strategy_defaults(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/floor/defaults/")
        assert resp.status_code == 200

    def test_strategies_unauthenticated(self, api_client):
        resp = api_client.get("/api/trading/strategies/")
        assert resp.status_code == 401
