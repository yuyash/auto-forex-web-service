from __future__ import annotations

import importlib

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.trading.views import StrategyView


class TestTradingViews:
    def test_strategy_view_requires_auth(self):
        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/")
        resp = StrategyView.as_view()(req)
        assert resp.status_code in {401, 403}

    def test_strategy_view_sorts_by_name(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(
            registry_module.registry,
            "get_all_strategies_info",
            lambda: {
                "b": {"config_schema": {"display_name": "Beta"}, "description": ""},
                "a": {"config_schema": {"display_name": "Alpha"}, "description": ""},
            },
        )

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/")
        force_authenticate(req, user=test_user)

        resp = StrategyView.as_view()(req)
        assert resp.status_code == 200
        data = resp.data
        names = [s["name"] for s in data["strategies"]]
        assert names == ["Alpha", "Beta"]
