"""Integration tests for candles endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestCandlesApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/candles/?instrument=EUR_USD"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_missing_instrument_400(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/candles/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 400

    def test_no_account_returns_400(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/candles/?instrument=EUR_USD"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "NO_OANDA_ACCOUNT"

    def test_returns_candles(self, live_server, auth_headers, oanda_account):
        _ = oanda_account
        url = f"{live_server.url}/api/market/candles/?instrument=EUR_USD&granularity=H1&count=2"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["instrument"] == "EUR_USD"
        assert data["granularity"] == "H1"
        assert isinstance(data["candles"], list)
