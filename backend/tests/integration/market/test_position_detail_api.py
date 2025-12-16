"""Integration tests for position detail/close endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestPositionDetailApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/positions/T1/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_get_requires_account_id(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/positions/T1/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 400

    def test_get_position(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/positions/T1/?account_id={oanda_account.id}"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "T1"
        assert data["account_db_id"] == oanda_account.id

    def test_close_position(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/positions/T1/"
        payload = {"account_id": oanda_account.id}
        resp = requests.patch(url, headers=auth_headers, json=payload, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]
        assert data["details"]["id"] == "CLOSE1"
