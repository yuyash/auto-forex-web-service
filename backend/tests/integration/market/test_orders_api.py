"""Integration tests for orders list/create endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestOrdersApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/orders/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_list_empty_when_no_accounts(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/orders/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_list_orders(self, live_server, auth_headers, oanda_account):
        _ = oanda_account
        url = f"{live_server.url}/api/market/orders/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(o["id"] == "O1" for o in data["results"])

    def test_create_market_order(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/orders/"
        payload = {
            "account_id": oanda_account.id,
            "instrument": "EUR_USD",
            "order_type": "market",
            "direction": "long",
            "units": 10,
        }
        resp = requests.post(url, headers=auth_headers, json=payload, timeout=10)

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "O1"
        assert data["instrument"] == "EUR_USD"
