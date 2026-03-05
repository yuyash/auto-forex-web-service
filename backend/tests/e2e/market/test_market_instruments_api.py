"""E2E tests for /api/market/instruments/ and /api/market/candles/granularities/."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestSupportedInstruments:
    def test_list_instruments(self, authenticated_client):
        resp = authenticated_client.get("/api/market/instruments/")
        assert resp.status_code == 200
        # Validate response structure
        assert "instruments" in resp.data
        assert "count" in resp.data
        assert resp.data["count"] > 0

    @skip_without_oanda
    def test_instrument_detail(self, authenticated_client, oanda_account):
        resp = authenticated_client.get("/api/market/instruments/USD_JPY/")
        assert resp.status_code == 200

    def test_instruments_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/instruments/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSupportedGranularities:
    def test_list_granularities(self, authenticated_client):
        resp = authenticated_client.get("/api/market/candles/granularities/")
        assert resp.status_code == 200
