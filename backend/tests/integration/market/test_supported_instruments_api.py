"""Integration tests for supported instruments endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestSupportedInstrumentsApi:
    def test_supported_instruments_public(self, live_server):
        url = f"{live_server.url}/api/market/instruments/"
        resp = requests.get(url, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "instruments" in data
        assert "count" in data
        assert data.get("source") in {"oanda", "fallback"}
