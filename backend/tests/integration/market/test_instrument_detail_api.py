"""Integration tests for instrument detail endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestInstrumentDetailApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/instruments/EUR_USD/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_returns_details(self, live_server, auth_headers, oanda_account):
        _ = oanda_account
        url = f"{live_server.url}/api/market/instruments/EUR_USD/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["instrument"] == "EUR_USD"
        assert data["source"] == "oanda"
