from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.market.services.oanda import OandaService, OrderDirection, Position


@pytest.mark.django_db
class TestOandaServiceUnit:
    def test_close_position_calls_position_close(self, monkeypatch, test_user):
        # Create a minimal OandaAccount without hitting the network.
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

        svc = OandaService(account)

        # Patch the v20.Context constructor used by OandaService so we don't need real network creds.
        import apps.market.services.oanda as oanda_module

        called = {}

        def _close(accountID, instrument, **kwargs):
            called.update({"accountID": accountID, "instrument": instrument, **kwargs})
            fill_tx = SimpleNamespace(time="2025-01-01T00:00:00Z", price="1.1001", id="1")
            return SimpleNamespace(status=200, longOrderFillTransaction=fill_tx)

        monkeypatch.setattr(
            oanda_module.v20,
            "Context",
            lambda **_kwargs: SimpleNamespace(position=SimpleNamespace(close=_close)),
        )

        # Recreate service so it picks up the patched Context.
        svc = OandaService(account)

        position = Position(
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("10"),
            average_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
            trade_ids=[],
            account_id=account.account_id,
        )

        svc.close_position(position, units=Decimal("10"))
        assert called["instrument"] == "EUR_USD"
        assert called["longUnits"] == "10"
