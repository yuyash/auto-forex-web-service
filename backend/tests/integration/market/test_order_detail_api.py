"""Integration tests for order detail/cancel endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestOrderDetailApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/orders/O1/?account_id=1"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_get_requires_account_id(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/orders/O1/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 400

    def test_get_order(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/orders/O1/?account_id={oanda_account.id}"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "O1"

    def test_cancel_order(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/orders/O1/?account_id={oanda_account.id}"
        resp = requests.delete(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]
        assert data["details"]["order_id"] == "O1"
