"""Integration tests for OANDA account detail endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestOandaAccountDetailApi:
    def test_requires_auth(self, live_server, oanda_account):
        url = f"{live_server.url}/api/market/accounts/{oanda_account.id}/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_not_found(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/accounts/999999/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 404

    def test_get_includes_live_data_flag(self, live_server, auth_headers, oanda_account):
        url = f"{live_server.url}/api/market/accounts/{oanda_account.id}/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == oanda_account.id
        assert "live_data" in data
