"""Integration tests for positions list/open endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestPositionsApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/positions/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_list_empty_when_no_accounts(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/positions/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_list_positions(self, live_server, auth_headers, oanda_account):
        _ = oanda_account
        url = f"{live_server.url}/api/market/positions/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(p["id"] == "T1" for p in data["results"])

    def test_open_position_market_order(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/positions/"
        payload = {
            "account_id": oanda_account.id,
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10,
        }
        resp = requests.put(url, headers=auth_headers, json=payload, timeout=10)

        assert resp.status_code == 201
        data = resp.json()
        assert data["instrument"] == "EUR_USD"
        assert data["account_db_id"] == oanda_account.id
