"""E2E tests for GET /api/market/candles/."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestMarketCandles:
    @skip_without_oanda
    def test_get_candles(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(
            "/api/market/candles/",
            {
                "account_id": oanda_account.id,
                "instrument": "USD_JPY",
                "granularity": "M1",
                "count": 5,
            },
        )
        assert resp.status_code == 200

    def test_candles_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/candles/")
        assert resp.status_code == 401
