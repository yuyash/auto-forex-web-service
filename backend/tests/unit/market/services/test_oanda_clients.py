"""Unit tests for focused OANDA client collaborators."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.market.models import TickData
from apps.market.services.oanda_clients import (
    OandaAccountClient,
    OandaContextFactory,
    OandaOrderClient,
    OandaPositionClient,
    OandaPricingStreamClient,
    OandaTradeClient,
    OandaTransactionClient,
)
from apps.market.services.oanda_types import (
    AccountDetails,
    LimitOrderRequest,
    MarketOrder,
    OcoOrder,
    OcoOrderRequest,
    OrderDirection,
    OrderState,
    OrderType,
    Position,
    StopOrderRequest,
)


class TestOandaContextFactory:
    """Tests for OANDA v20 context construction helpers."""

    def test_stream_hostname_converts_rest_hostnames(self):
        factory = OandaContextFactory()

        assert factory.stream_hostname("api-fxpractice.oanda.com") == (
            "stream-fxpractice.oanda.com"
        )
        assert factory.stream_hostname("stream-fxpractice.oanda.com") == (
            "stream-fxpractice.oanda.com"
        )
        assert factory.stream_hostname("") == ""


class TestOandaAccountClient:
    """Tests for account-resource caching and parsing."""

    def test_get_resource_fetches_then_reuses_cached_value(self):
        response = SimpleNamespace(
            status=200,
            body={"account": SimpleNamespace(id="101-001")},
        )
        service = SimpleNamespace(
            api=SimpleNamespace(account=SimpleNamespace(get=MagicMock(return_value=response))),
            account=SimpleNamespace(account_id="101-001"),
            _account_resource_cache=None,
            _account_object_to_dict=MagicMock(return_value={"id": "101-001"}),
        )
        client = OandaAccountClient(service)

        first = client.get_resource()
        second = client.get_resource()

        assert first == {"id": "101-001"}
        assert second == {"id": "101-001"}
        service.api.account.get.assert_called_once_with("101-001")

    def test_get_details_maps_account_resource(self):
        service = SimpleNamespace(
            account=SimpleNamespace(account_id="101-001"),
            get_account_resource=MagicMock(
                return_value={
                    "currency": "JPY",
                    "balance": "1000.5",
                    "unrealizedPL": "-2.5",
                    "NAV": "998",
                    "marginUsed": "10",
                    "marginAvailable": "988",
                    "positionValue": "250",
                    "openTradeCount": 2,
                    "openPositionCount": 1,
                    "pendingOrderCount": 0,
                    "lastTransactionID": "42",
                }
            ),
        )

        details = OandaAccountClient(service).get_details()

        assert isinstance(details, AccountDetails)
        assert details.account_id == "101-001"
        assert details.currency == "JPY"
        assert details.balance == Decimal("1000.5")
        assert details.last_transaction_id == "42"

    def test_position_mode_uses_hedging_flag(self):
        service = SimpleNamespace(
            account=SimpleNamespace(account_id="101-001"),
            get_account_resource=MagicMock(return_value={"hedgingEnabled": True}),
        )

        assert OandaAccountClient(service).get_position_mode() == "hedging"


class TestOandaOrderClient:
    """Tests for order client behavior."""

    def test_create_oco_order_composes_limit_and_stop_orders(self):
        limit_order = MagicMock(order_id="L1", create_time=datetime(2026, 1, 1, tzinfo=UTC))
        stop_order = MagicMock(order_id="S1")
        service = SimpleNamespace(
            create_limit_order=MagicMock(return_value=limit_order),
            create_stop_order=MagicMock(return_value=stop_order),
        )
        request = OcoOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
            limit_price=Decimal("1.1"),
            stop_price=Decimal("1.0"),
        )

        order = OandaOrderClient(service).create_oco_order(request)

        assert isinstance(order, OcoOrder)
        assert order.order_id == "OCO-L1-S1"
        assert order.limit_order is limit_order
        assert order.stop_order is stop_order
        service.create_limit_order.assert_called_once_with(
            LimitOrderRequest(instrument="EUR_USD", units=Decimal("1000"), price=Decimal("1.1"))
        )
        service.create_stop_order.assert_called_once_with(
            StopOrderRequest(instrument="EUR_USD", units=Decimal("1000"), price=Decimal("1.0"))
        )

    def test_get_order_history_fetches_and_parses_orders(self):
        raw_order = {"id": "1"}
        response = SimpleNamespace(status=200, body={"orders": [raw_order]})
        service = SimpleNamespace(
            api=SimpleNamespace(order=SimpleNamespace(list=MagicMock(return_value=response))),
            account=SimpleNamespace(account_id="101-001"),
            _parse_order=MagicMock(return_value="parsed"),
        )

        orders = OandaOrderClient(service).get_order_history(
            instrument="EUR_USD",
            count=10,
            state="FILLED",
        )

        assert orders == ["parsed"]
        service.api.order.list.assert_called_once_with(
            "101-001",
            count=10,
            state="FILLED",
            instrument="EUR_USD",
        )
        service._parse_order.assert_called_once_with(raw_order)


class TestOandaTradeClient:
    """Tests for trade client behavior."""

    def test_get_open_trades_uses_open_state(self):
        service = SimpleNamespace()
        client = OandaTradeClient(service)
        client.get_trades = MagicMock(return_value=["trade"])

        assert client.get_open_trades(instrument="USD_JPY") == ["trade"]
        client.get_trades.assert_called_once_with(instrument="USD_JPY", state="OPEN")


class TestOandaPositionClient:
    """Tests for position client behavior."""

    def test_close_position_uses_dry_run_simulator_when_enabled(self):
        position = Position(
            instrument="USD_JPY",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            average_price=Decimal("150"),
            unrealized_pnl=Decimal("0"),
            trade_ids=[],
            account_id="dry",
        )
        expected = MarketOrder(
            order_id="DRY",
            instrument="USD_JPY",
            order_type=OrderType.MARKET,
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            price=Decimal("150.1"),
            state=OrderState.FILLED,
            time_in_force="FOK",
            create_time=datetime(2026, 1, 1, tzinfo=UTC),
            fill_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
        service = SimpleNamespace(
            dry_run=True,
            _dry_run_simulator=SimpleNamespace(
                simulate_position_close=MagicMock(return_value=expected)
            ),
        )

        order = OandaPositionClient(service).close_position(
            position,
            units=Decimal("500"),
            override_price=Decimal("150.1"),
        )

        assert order is expected
        service._dry_run_simulator.simulate_position_close.assert_called_once_with(
            position,
            Decimal("500"),
            override_price=Decimal("150.1"),
        )


class TestOandaTransactionClient:
    """Tests for transaction-history client behavior."""

    def test_transaction_history_parses_inline_transactions(self):
        raw_transaction = {"id": "1"}
        response = SimpleNamespace(status=200, body={"transactions": [raw_transaction]})
        service = SimpleNamespace(
            api=SimpleNamespace(transaction=SimpleNamespace(list=MagicMock(return_value=response))),
            account=SimpleNamespace(account_id="101-001"),
            _parse_transaction=MagicMock(return_value="parsed"),
        )

        transactions = OandaTransactionClient(service).get_transaction_history(page_size=10)

        assert transactions == ["parsed"]
        service.api.transaction.list.assert_called_once_with("101-001", pageSize=10)
        service._parse_transaction.assert_called_once_with(raw_transaction)


class TestOandaPricingStreamClient:
    """Tests for pricing stream client behavior."""

    def test_stream_pricing_ticks_parses_dict_price_messages(self):
        response = SimpleNamespace(
            status=200,
            parts=MagicMock(
                return_value=[
                    (
                        "pricing.ClientPrice",
                        {
                            "type": "PRICE",
                            "instrument": "EUR_USD",
                            "time": "2026-01-01T00:00:00Z",
                            "bids": [{"price": "1.1"}],
                            "asks": [{"price": "1.2"}],
                        },
                    )
                ]
            ),
        )
        service = SimpleNamespace(
            stream_api=SimpleNamespace(
                pricing=SimpleNamespace(stream=MagicMock(return_value=response))
            ),
            account=SimpleNamespace(account_id="101-001"),
            _parse_iso_datetime=MagicMock(return_value=datetime(2026, 1, 1, tzinfo=UTC)),
        )

        ticks = list(OandaPricingStreamClient(service).stream_pricing_ticks(["EUR_USD"]))

        assert len(ticks) == 1
        assert isinstance(ticks[0], TickData)
        assert ticks[0].instrument == "EUR_USD"
        assert ticks[0].mid == Decimal("1.15")
        service.stream_api.pricing.stream.assert_called_once_with(
            "101-001",
            snapshot=True,
            instruments="EUR_USD",
        )
