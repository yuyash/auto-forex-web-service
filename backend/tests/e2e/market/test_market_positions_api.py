"""E2E tests for /api/market/positions/."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestMarketPositions:
    @skip_without_oanda
    def test_list_positions(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/positions/",
            {"account_id": oanda_account.id},
        )
        assert resp.status_code == 200

    @skip_without_oanda
    def test_get_position_detail(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/positions/dummy-trade-id/",
            {"account_id": oanda_account.id},
        )
        assert resp.status_code in (200, 404)

    @skip_without_oanda
    def test_close_position(self, authenticated_client, oanda_account):
        resp = authenticated_client.patch(
            "/api/market/positions/dummy-trade-id/",
            {"account_id": oanda_account.id},
            format="json",
        )
        assert resp.status_code in (200, 404)

    def test_positions_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/positions/")
        assert resp.status_code == 401
