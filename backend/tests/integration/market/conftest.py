from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass
class _DummyV20Response:
    status: int = 200
    body: dict[str, Any] | None = None


class _DummyMid:
    def __init__(self, o: str, h: str, low: str, c: str) -> None:
        self.o = o
        self.h = h
        self.l = low  # noqa: E741
        self.c = c


class _DummyCandle:
    def __init__(self, t: str) -> None:
        self.complete = True
        self.mid = _DummyMid("1.1000", "1.1100", "1.0900", "1.1050")
        self.time = t
        self.volume = 123


class _DummyInstrumentApi:
    def candles(self, instrument: str, **_params):
        _ = instrument
        candles = [
            _DummyCandle("2025-01-01T00:00:00Z"),
            _DummyCandle("2025-01-01T01:00:00Z"),
        ]
        return _DummyV20Response(status=200, body={"candles": candles})


class _DummyAccountInstrument:
    def __init__(self, name: str) -> None:
        self.name = name


class _DummyAccountApi:
    def instruments(self, _account_id: str, instruments: str | None = None):
        if instruments:
            # Minimal object set for InstrumentDetailView when we don't stub it.
            instr = SimpleNamespace(
                name=instruments,
                displayName=instruments,
                type="CURRENCY",
                pipLocation=-4,
                displayPrecision=5,
                tradeUnitsPrecision=0,
                minimumTradeSize=Decimal("1"),
                maximumTradeUnits=Decimal("1000000"),
                maximumPositionSize=Decimal("1000000"),
                maximumOrderUnits=Decimal("1000000"),
                marginRate=Decimal("0.02"),
                tags=[],
                financing=None,
            )
            return _DummyV20Response(status=200, body={"instruments": [instr]})

        return _DummyV20Response(
            status=200,
            body={
                "instruments": [
                    _DummyAccountInstrument("EUR_USD"),
                    _DummyAccountInstrument("GBP_USD"),
                    _DummyAccountInstrument("USD_JPY"),
                ]
            },
        )


class _DummyPricingPoint:
    def __init__(self, price: str) -> None:
        self.price = price


class _DummyPricingApi:
    def get(self, _account_id: str, _instruments: str):
        _ = _instruments
        price = SimpleNamespace(
            bids=[_DummyPricingPoint("1.1000")],
            asks=[_DummyPricingPoint("1.1002")],
            tradeable=True,
            time="2025-01-01T00:00:00Z",
        )
        return _DummyV20Response(status=200, body={"prices": [price]})


class _DummyV20Context:
    def __init__(self, **_kwargs):
        self.instrument = _DummyInstrumentApi()
        self.account = _DummyAccountApi()
        self.pricing = _DummyPricingApi()


class _E:
    def __init__(self, value: str) -> None:
        self.value = value


class _DummyOandaService:
    def __init__(self, account):
        self.account = account

    def get_account_details(self):
        return SimpleNamespace(
            balance=Decimal("1000"),
            margin_used=Decimal("10"),
            margin_available=Decimal("990"),
            unrealized_pl=Decimal("0"),
            nav=Decimal("1000"),
            open_trade_count=1,
            open_position_count=1,
            pending_order_count=0,
        )

    def get_open_trades(self, instrument: str | None = None):
        _ = instrument
        return [
            SimpleNamespace(
                trade_id="T1",
                instrument="EUR_USD",
                direction=_E("long"),
                units=Decimal("10"),
                entry_price=Decimal("1.1000"),
                unrealized_pnl=Decimal("0"),
                open_time=datetime(2025, 1, 1, tzinfo=UTC),
                state="OPEN",
            )
        ]

    def close_trade(self, trade, units=None):
        _ = trade
        _ = units
        return SimpleNamespace(
            order_id="CLOSE1",
            instrument="EUR_USD",
            order_type=_E("market"),
            direction=_E("long"),
            units=Decimal("10"),
            price=Decimal("1.1001"),
            state=_E("filled"),
            fill_time=datetime(2025, 1, 1, tzinfo=UTC),
        )

    def create_market_order(self, _req):
        return SimpleNamespace(
            order_id="O1",
            instrument=getattr(_req, "instrument", "EUR_USD"),
            order_type=_E("market"),
            direction=_E("long"),
            units=Decimal(str(getattr(_req, "units", 1))),
            price=Decimal("1.1001"),
            state=_E("filled"),
            time_in_force="FOK",
            create_time=datetime(2025, 1, 1, tzinfo=UTC),
            fill_time=datetime(2025, 1, 1, tzinfo=UTC),
            cancel_time=None,
        )

    def create_limit_order(self, _req):
        return self.create_market_order(_req)

    def create_stop_order(self, _req):
        return self.create_market_order(_req)

    def get_pending_orders(self, instrument: str | None = None):
        _ = instrument
        return []

    def get_order_history(self, instrument: str | None = None, count: int = 50, state: str = "ALL"):
        _ = instrument
        _ = count
        _ = state
        return [
            SimpleNamespace(
                order_id="O1",
                instrument="EUR_USD",
                order_type=_E("market"),
                direction=_E("long"),
                units=Decimal("10"),
                price=Decimal("1.1001"),
                state=_E("filled"),
                time_in_force="FOK",
                create_time=datetime(2025, 1, 1, tzinfo=UTC),
                fill_time=datetime(2025, 1, 1, tzinfo=UTC),
                cancel_time=None,
            )
        ]

    def get_order(self, order_id: str):
        _ = order_id
        return self.get_order_history()[0]

    def cancel_order(self, order):
        _ = order
        return SimpleNamespace(
            order_id="O1",
            transaction_id="TX1",
            cancel_time=datetime(2025, 1, 1, tzinfo=UTC),
            state=_E("cancelled"),
        )


@pytest.fixture(autouse=True)
def _mock_oanda_and_v20(monkeypatch):
    """Prevent integration tests from hitting real OANDA/v20 network calls."""

    import apps.market.views as market_views

    monkeypatch.setattr(market_views.v20, "Context", _DummyV20Context)
    monkeypatch.setattr(market_views, "OandaService", _DummyOandaService)

    # Avoid needing to fully model v20 instrument objects in InstrumentDetailView.
    def _fake_fetch(_self, request, instrument: str):
        _ = _self
        _ = request
        return {
            "instrument": instrument,
            "display_name": instrument,
            "type": "CURRENCY",
            "pip_location": -4,
            "pip_value": 0.0001,
            "display_precision": 5,
            "trade_units_precision": 0,
            "minimum_trade_size": "1",
            "maximum_trade_units": "1000000",
            "maximum_position_size": "1000000",
            "maximum_order_units": "1000000",
            "margin_rate": "0.02",
            "leverage": "1:50",
            "guaranteed_stop_loss_order_mode": "DISABLED",
            "tags": [],
            "financing": None,
            "current_pricing": None,
        }

    monkeypatch.setattr(market_views.InstrumentDetailView, "_fetch_instrument_details", _fake_fetch)


@pytest.fixture
def oanda_account(db, test_user):
    _ = db
    from apps.market.models import OandaAccount

    account = OandaAccount.objects.create(
        user=test_user,
        account_id="101-001-0000000-001",
        api_token="",
        api_type="practice",
        jurisdiction="OTHER",
        currency="USD",
        is_active=True,
        is_default=True,
    )
    account.set_api_token("token")
    account.save(update_fields=["api_token"])
    return account
