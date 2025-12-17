"""Integration tests for supported instruments endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestSupportedInstrumentsApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/market/instruments/"
        resp = requests.get(url, timeout=10)

        assert resp.status_code in {401, 403}

    def test_supported_instruments_authenticated(self, live_server, auth_headers):
        url = f"{live_server.url}/api/market/instruments/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "instruments" in data
        assert "count" in data
        assert data.get("source") in {"oanda", "fallback"}
