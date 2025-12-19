from __future__ import annotations

import importlib

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.trading.views import StrategyDefaultsView, StrategyView


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

    def test_strategy_defaults_view_requires_auth(self):
        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/floor/defaults/")
        resp = StrategyDefaultsView.as_view()(req, strategy_id="floor")
        assert resp.status_code in {401, 403}

    def test_strategy_defaults_view_returns_404_for_unknown_strategy(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(registry_module.registry, "is_registered", lambda _key: False)

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/nope/defaults/")
        force_authenticate(req, user=test_user)

        resp = StrategyDefaultsView.as_view()(req, strategy_id="nope")
        assert resp.status_code == 404

    def test_strategy_defaults_view_returns_defaults(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(registry_module.registry, "is_registered", lambda _key: True)
        monkeypatch.setattr(
            registry_module.registry,
            "get_all_strategies_info",
            lambda: {
                "floor": {
                    "config_schema": {
                        "properties": {
                            "instrument": {"type": "string"},
                            "max_layers": {"type": "integer"},
                        }
                    },
                    "description": "",
                }
            },
        )

        from django.conf import settings

        monkeypatch.setattr(
            settings,
            "TRADING_FLOOR_STRATEGY_DEFAULTS",
            {"instrument": "USD_JPY", "max_layers": 3, "extra": 123},
            raising=False,
        )

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/floor/defaults/")
        force_authenticate(req, user=test_user)

        resp = StrategyDefaultsView.as_view()(req, strategy_id="floor")
        assert resp.status_code == 200
        data = resp.data
        assert data["strategy_id"] == "floor"
        assert data["defaults"] == {"instrument": "USD_JPY", "max_layers": 3}
