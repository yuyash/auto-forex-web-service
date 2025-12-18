"""Integration tests for trading strategies endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestTradingStrategiesApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/strategies/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_returns_sorted_strategies(self, live_server, auth_headers):
        url = f"{live_server.url}/api/trading/strategies/"
        resp = requests.get(url, headers=auth_headers, timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "count" in data

        strategies = data["strategies"]
        assert isinstance(strategies, list)
        assert data["count"] == len(strategies)

        # sanity-check shape and ordering by display name
        names = []
        for item in strategies:
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "config_schema" in item
            names.append(item["name"])

        assert names == sorted(names)
