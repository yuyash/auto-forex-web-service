from __future__ import annotations

from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

from apps.market.views import MarketStatusView, SupportedGranularitiesView, SupportedInstrumentsView


class TestMarketViews:
    def test_market_status_requires_auth(self) -> None:
        factory = APIRequestFactory()
        req = factory.get("/api/market/market/status/")
        resp = MarketStatusView.as_view()(req)
        assert resp.status_code in {401, 403}

    def test_market_status_returns_keys(self, test_user) -> None:
        factory = APIRequestFactory()
        req = factory.get("/api/market/market/status/")
        force_authenticate(req, user=test_user)
        resp = MarketStatusView.as_view()(req)
        assert resp.status_code == 200
        data = resp.data
        assert "is_open" in data
        assert "active_sessions" in data
        assert "next_event" in data

    def test_supported_granularities_requires_auth(self, monkeypatch) -> None:
        monkeypatch.setattr(
            SupportedGranularitiesView,
            "_fetch_granularities_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/candles/granularities/")
        resp = SupportedGranularitiesView.as_view()(req)
        assert resp.status_code in {401, 403}

    def test_supported_granularities_fallback(self, monkeypatch, test_user) -> None:
        monkeypatch.setattr(
            SupportedGranularitiesView,
            "_fetch_granularities_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/candles/granularities/")
        force_authenticate(req, user=test_user)
        resp = SupportedGranularitiesView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["source"] == "standard"
        assert resp.data["count"] == len(resp.data["granularities"])

    def test_supported_instruments_requires_auth(self, monkeypatch) -> None:
        monkeypatch.setattr(
            SupportedInstrumentsView,
            "_fetch_instruments_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/instruments/")
        resp = SupportedInstrumentsView.as_view()(req)

        assert resp.status_code in {401, 403}

    def test_supported_instruments_fallback(self, monkeypatch, test_user) -> None:
        monkeypatch.setattr(
            SupportedInstrumentsView,
            "_fetch_instruments_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/instruments/")
        force_authenticate(req, user=test_user)
        resp = SupportedInstrumentsView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["source"] == "fallback"
        assert resp.data["count"] == len(resp.data["instruments"])
