"""E2E tests for GET /api/market/health/oanda/."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestOandaApiHealth:
    @skip_without_oanda
    def test_oanda_health(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/health/oanda/",
            {"account_id": oanda_account.id},
        )
        assert resp.status_code == 200

    def test_oanda_health_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/health/oanda/")
        assert resp.status_code == 401
