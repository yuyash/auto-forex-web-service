"""E2E tests for GET /api/health/."""

import pytest


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/api/health/")
        assert resp.status_code == 200
        assert "status" in resp.data
