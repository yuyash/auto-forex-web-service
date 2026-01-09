from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.market.services.health import OandaHealthCheckService


@pytest.mark.django_db
class TestOandaHealthCheckService:
    def test_check_persists_success(self, monkeypatch, test_user):
        from apps.market.models import OandaAccount

        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-099",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
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

        row = OandaHealthCheckService(account).check()
        assert row.account_id == account.id  # type: ignore[attr-defined]
        assert row.is_available is True
        assert row.http_status == 200
        assert row.latency_ms is not None
        assert row.error_message == ""

    def test_check_persists_failure_status(self, monkeypatch, test_user):
        from apps.market.models import OandaAccount

        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-099",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
        )
        account.set_api_token("token")
        account.save(update_fields=["api_token"])

        import apps.market.services.health as health_module

        def _get(_account_id):
            return SimpleNamespace(status=401, body={"errorMessage": "Invalid token"})

        monkeypatch.setattr(
            health_module.v20,
            "Context",
            lambda **_kwargs: SimpleNamespace(account=SimpleNamespace(get=_get)),
        )

        row = OandaHealthCheckService(account).check()
        assert row.is_available is False
        assert row.http_status == 401
        assert "status" in str(row.error_message)
