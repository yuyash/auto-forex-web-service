from __future__ import annotations

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.market.views import (
    MarketStatusView,
    OandaApiHealthView,
    SupportedGranularitiesView,
    SupportedInstrumentsView,
)


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

    def test_oanda_health_requires_auth(self) -> None:
        factory = APIRequestFactory()
        req = factory.get("/api/market/health/oanda/")
        resp = OandaApiHealthView.as_view()(req)
        assert resp.status_code in {401, 403}

    def test_oanda_health_get_returns_null_when_no_checks(self, test_user) -> None:
        from apps.market.models import OandaAccount

        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-099",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
            is_default=True,
        )
        account.set_api_token("token")
        account.save(update_fields=["api_token"])

        factory = APIRequestFactory()
        req = factory.get("/api/market/health/oanda/")
        force_authenticate(req, user=test_user)
        resp = OandaApiHealthView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["account"]["account_id"] == account.account_id
        assert resp.data["status"] is None

    def test_oanda_health_post_triggers_check(self, monkeypatch, test_user) -> None:
        from types import SimpleNamespace

        from apps.market.models import OandaAccount

        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-099",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
            is_default=True,
        )
        account.set_api_token("token")
        account.save(update_fields=["api_token"])

        import apps.market.services.health as health_module

        def _get(_account_id):
            return SimpleNamespace(status=200, body={"account": {}})

        monkeypatch.setattr(
            health_module.v20,
            "Context",
            lambda **_kwargs: SimpleNamespace(account=SimpleNamespace(get=_get)),
        )

        factory = APIRequestFactory()
        req = factory.post("/api/market/health/oanda/")
        force_authenticate(req, user=test_user)
        resp = OandaApiHealthView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["status"]["is_available"] is True
        assert resp.data["status"]["http_status"] == 200
