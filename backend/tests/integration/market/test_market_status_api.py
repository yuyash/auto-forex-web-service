"""Integration tests for market status endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestMarketStatusApi:
    def test_market_status_public(self, live_server):
        url = f"{live_server.url}/api/market/market/status/"
        resp = requests.get(url, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "is_open" in data
        assert "active_sessions" in data
        assert "next_event" in data
