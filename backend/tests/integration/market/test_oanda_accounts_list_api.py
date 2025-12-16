"""Integration tests for OANDA accounts list/create endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestOandaAccountsListApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/accounts/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_list_empty(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/accounts/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_create_account(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/accounts/"
        payload = {
            "account_id": "101-001-0000000-777",
            "api_token": "token-777",
            "api_type": "practice",
            "jurisdiction": "OTHER",
            "currency": "USD",
            "is_active": True,
        }
        resp = requests.post(url, headers=auth_headers, json=payload, timeout=10)

        assert resp.status_code == 201
        data = resp.json()
        assert data["account_id"] == "101-001-0000000-777"
