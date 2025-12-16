from __future__ import annotations

from rest_framework.test import APIRequestFactory

from apps.market.views import MarketStatusView, SupportedGranularitiesView, SupportedInstrumentsView


class TestPublicMarketViews:
    def test_market_status_returns_keys(self) -> None:
        factory = APIRequestFactory()
        req = factory.get("/api/market/market/status/")
        resp = MarketStatusView.as_view()(req)
        assert resp.status_code == 200
        data = resp.data
        assert "is_open" in data
        assert "active_sessions" in data
        assert "next_event" in data

    def test_supported_granularities_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr(
            SupportedGranularitiesView,
            "_fetch_granularities_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/candles/granularities/")
        resp = SupportedGranularitiesView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["source"] == "standard"
        assert resp.data["count"] == len(resp.data["granularities"])

    def test_supported_instruments_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr(
            SupportedInstrumentsView,
            "_fetch_instruments_from_oanda",
            lambda self: None,
        )
        factory = APIRequestFactory()
        req = factory.get("/api/market/instruments/")
        resp = SupportedInstrumentsView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["source"] == "fallback"
        assert resp.data["count"] == len(resp.data["instruments"])
