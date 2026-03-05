"""E2E tests for /api/market/orders/."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestMarketOrders:
    @skip_without_oanda
    def test_list_orders(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/orders/",
            {"account_id": oanda_account.id},
        )
        assert resp.status_code == 200

    @skip_without_oanda
    def test_create_market_order(self, authenticated_client, oanda_account):
        resp = authenticated_client.post(
            "/api/market/orders/",
            {
                "account_id": oanda_account.id,
                "instrument": "USD_JPY",
                "units": 1,
                "order_type": "market",
            },
            format="json",
        )
        # 200/201 = success, 400 = validation, 422 = compliance
        assert resp.status_code in (200, 201, 400, 422), resp.data

    @skip_without_oanda
    def test_get_order_detail(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/orders/dummy-order-id/",
            {"account_id": oanda_account.id},
        )
        # 200 if found, 404 if not — both are valid
        assert resp.status_code in (200, 404)

    def test_orders_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/orders/")
        assert resp.status_code == 401
