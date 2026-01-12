"""Integration tests for trading strategy defaults endpoint."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestTradingStrategyDefaultsApi:
    def test_requires_auth(self, live_server):
        url = f"{live_server.url}/api/trading/strategies/floor/defaults/"
        resp = requests.get(url, timeout=10)
        assert resp.status_code in {401, 403}

    def test_returns_defaults_for_floor(self, live_server, auth_headers):
        url = f"{live_server.url}/api/trading/strategies/floor/defaults/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 200

        data = resp.json()
        assert data["strategy_id"] == "floor"
        assert "defaults" in data
        defaults = data["defaults"]
        assert isinstance(defaults, dict)

        # sanity check: should include at least a few known floor keys
        assert "max_layers" in defaults
        assert "base_lot_size" in defaults
        assert "take_profit_pips" in defaults

    def test_returns_404_for_unknown_strategy(self, live_server, auth_headers):
        url = f"{live_server.url}/api/trading/strategies/does-not-exist/defaults/"
        resp = requests.get(url, headers=auth_headers, timeout=10)
        assert resp.status_code == 404
