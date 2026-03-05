"""E2E tests for GET /api/market/market/status/."""

import pytest


@pytest.mark.django_db
class TestMarketStatus:
    def test_get_market_status(self, authenticated_client):
        resp = authenticated_client.get("/api/market/market/status/")
        assert resp.status_code == 200
        # Validate response structure
        assert "is_open" in resp.data
        assert "current_time_utc" in resp.data
        assert "active_sessions" in resp.data
        assert "is_weekend" in resp.data

    def test_market_status_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/market/status/")
        assert resp.status_code == 401
