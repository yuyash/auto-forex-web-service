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

    def test_get_account_details_supports_v20_account_object(self, monkeypatch, test_user):
        from apps.market.models import OandaAccount

        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-36034971-001",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
        )
        account.set_api_token("token")
        account.save(update_fields=["api_token"])

        # Return a dict instead of an object since _account_object_to_dict expects dict or object with _properties
        dummy_account_dict = {
            "currency": "USD",
            "balance": "1000.01",
            "unrealizedPL": "-1.23",
            "NAV": "998.78",
            "marginUsed": "10",
            "marginAvailable": "988.78",
            "positionValue": "0",
            "openTradeCount": 1,
            "openPositionCount": 2,
            "pendingOrderCount": 3,
            "lastTransactionID": "42",
        }

        def _get(_account_id):
            return SimpleNamespace(status=200, body={"account": dummy_account_dict})

        import apps.market.services.oanda as oanda_module

        monkeypatch.setattr(
            oanda_module.v20,
            "Context",
            lambda **_kwargs: SimpleNamespace(account=SimpleNamespace(get=_get)),
        )

        svc = OandaService(account)
        details = svc.get_account_details()

        assert details.account_id == "101-001-36034971-001"
        assert details.currency == "USD"
        assert details.balance == Decimal("1000.01")
        assert details.unrealized_pl == Decimal("-1.23")
        assert details.nav == Decimal("998.78")
        assert details.margin_used == Decimal("10")
        assert details.margin_available == Decimal("988.78")
        assert details.position_value == Decimal("0")
        assert details.open_trade_count == 1
        assert details.open_position_count == 2
        assert details.pending_order_count == 3
        assert details.last_transaction_id == "42"
