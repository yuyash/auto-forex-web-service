"""Unit tests for focused OANDA client collaborators."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.market.services.oanda_clients import (
    OandaAccountClient,
    OandaContextFactory,
    OandaOrderClient,
    OandaPositionClient,
    OandaPricingStreamClient,
    OandaTradeClient,
    OandaTransactionClient,
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

    def test_account_facade_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaAccountClient(service)

        client.get_details()
        client.get_hedging_enabled()
        client.get_position_mode()

        service._get_account_details_impl.assert_called_once_with()
        service._get_account_hedging_enabled_impl.assert_called_once_with()
        service._get_account_position_mode_impl.assert_called_once_with()


class TestOandaOrderClient:
    """Tests for order client delegation."""

    def test_order_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaOrderClient(service)

        client.cancel_order("order")
        client.create_limit_order("limit")
        client.create_market_order("market", override_price="1.1")
        client.create_stop_order("stop")
        client.create_oco_order("oco")
        client.get_pending_orders(instrument="EUR_USD")
        client.get_order_history(instrument="EUR_USD", count=10, state="FILLED")
        client.get_order("123")

        service._cancel_order_impl.assert_called_once_with("order")
        service._create_limit_order_impl.assert_called_once_with("limit")
        service._create_market_order_impl.assert_called_once_with(
            "market",
            override_price="1.1",
        )
        service._create_stop_order_impl.assert_called_once_with("stop")
        service._create_oco_order_impl.assert_called_once_with("oco")
        service._get_pending_orders_impl.assert_called_once_with(instrument="EUR_USD")
        service._get_order_history_impl.assert_called_once_with(
            instrument="EUR_USD",
            count=10,
            state="FILLED",
        )
        service._get_order_impl.assert_called_once_with("123")


class TestOandaTradeClient:
    """Tests for trade client delegation."""

    def test_trade_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaTradeClient(service)

        client.close_trade(trade="trade", units="100")
        client.get_trades(instrument="USD_JPY", state="CLOSED", count=25)
        client.get_open_trades(instrument="USD_JPY")

        service._close_trade_impl.assert_called_once_with(trade="trade", units="100")
        service._get_trades_impl.assert_called_once_with(
            instrument="USD_JPY",
            state="CLOSED",
            count=25,
        )
        service._get_open_trades_impl.assert_called_once_with(instrument="USD_JPY")


class TestOandaPositionClient:
    """Tests for position client delegation."""

    def test_position_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaPositionClient(service)

        client.close_position(position="position", units="100", override_price="1.2")
        client.get_open_positions(instrument="GBP_USD")

        service._close_position_impl.assert_called_once_with(
            position="position",
            units="100",
            override_price="1.2",
        )
        service._get_open_positions_impl.assert_called_once_with(instrument="GBP_USD")


class TestOandaTransactionClient:
    """Tests for transaction client delegation."""

    def test_transaction_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaTransactionClient(service)

        client.get_transaction_history(page_size=10, transaction_type="ORDER_FILL")

        service._get_transaction_history_impl.assert_called_once_with(
            from_time=None,
            to_time=None,
            page_size=10,
            transaction_type="ORDER_FILL",
        )


class TestOandaPricingStreamClient:
    """Tests for pricing stream client delegation."""

    def test_stream_methods_delegate_to_service_implementation(self):
        service = MagicMock()
        client = OandaPricingStreamClient(service)

        client.stream_pricing_ticks(
            ["EUR_USD"],
            snapshot=False,
            include_heartbeats=True,
        )

        service._stream_pricing_ticks_impl.assert_called_once_with(
            ["EUR_USD"],
            snapshot=False,
            include_heartbeats=True,
        )
