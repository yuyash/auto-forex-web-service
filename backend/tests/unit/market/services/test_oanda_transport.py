"""Unit tests for OANDA transport retry behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.market.services.oanda import OandaAPIError
from apps.market.services.oanda_transport import OandaOrderClientExtensions, OandaOrderTransport


class OandaTransportTestFactory:
    """Build OANDA transport test doubles."""

    def build(self, *, responses, transaction_response=None):
        api = SimpleNamespace(
            order=SimpleNamespace(
                create=MagicMock(side_effect=responses),
                get=MagicMock(),
            )
        )
        if transaction_response is not None:
            api.transaction = SimpleNamespace(
                list=MagicMock(return_value=transaction_response),
            )
        account = SimpleNamespace(account_id="acct-1", user=SimpleNamespace(id=1))
        event_service = SimpleNamespace(log_trading_event=MagicMock())
        sleep = MagicMock()
        transport = OandaOrderTransport(
            api=api,
            account=account,
            event_service=event_service,
            logger=SimpleNamespace(
                debug=MagicMock(),
                warning=MagicMock(),
                error=MagicMock(),
            ),
            max_retries=3,
            retry_delay=0,
            max_retry_delay=1,
            error_class=OandaAPIError,
            sleep_func=sleep,
            randbelow_func=MagicMock(return_value=0),
        )
        return transport, api, event_service, sleep


class TestOandaOrderTransport:
    """Verify OANDA order transport retry and recovery behavior."""

    def test_execute_order_retries_retryable_status_then_succeeds(self):
        transport, api, event_service, sleep = OandaTransportTestFactory().build(
            responses=[
                SimpleNamespace(status=429, body={"errorMessage": "rate limit"}),
                SimpleNamespace(status=201, body={}),
            ]
        )

        response = transport.execute_order({"instrument": "USD_JPY"})

        assert response.status == 201
        assert api.order.create.call_count == 2
        sleep.assert_called_once()
        event_service.log_trading_event.assert_not_called()

    def test_execute_order_logs_failure_for_non_retryable_status(self):
        transport, api, event_service, sleep = OandaTransportTestFactory().build(
            responses=[SimpleNamespace(status=400, body={"errorMessage": "bad request"})]
        )

        with pytest.raises(OandaAPIError, match="Order submission failed"):
            transport.execute_order({"instrument": "BAD"})

        api.order.create.assert_called_once()
        sleep.assert_not_called()
        event_service.log_trading_event.assert_called_once()

    def test_order_client_extensions_apply_sanitized_client_id(self):
        order_data = {"instrument": "EUR_USD"}
        client_id = OandaOrderClientExtensions().apply(order_data, "abc 123/$")

        assert client_id == "abc-123"
        assert order_data["clientExtensions"]["id"] == "abc-123"

    def test_execute_order_recovers_existing_order_by_client_id_after_create_failure(self):
        transport, api, event_service, sleep = OandaTransportTestFactory().build(
            responses=[SimpleNamespace(status=400, body={"errorMessage": "duplicate client id"})]
        )
        api.order.get.return_value = self._filled_order_response(trade_id="T100")

        response = transport.execute_order(
            {"instrument": "EUR_USD", "clientExtensions": {"id": "cid-1"}}
        )

        assert response.status == 200
        assert response.orderFillTransaction["tradeOpened"]["tradeID"] == "T100"
        api.order.get.assert_called_once_with("acct-1", "@cid-1")
        sleep.assert_not_called()
        event_service.log_trading_event.assert_not_called()

    def test_recovery_uses_transaction_fill_trade_id_when_order_lacks_trade_id(self):
        transaction_response = SimpleNamespace(
            status=200,
            body={
                "transactions": [
                    {
                        "id": "200",
                        "type": "ORDER_FILL",
                        "clientOrderID": "cid-1",
                        "time": "2026-05-08T00:00:02Z",
                        "price": "1.1010",
                        "tradeOpened": {"tradeID": "T200"},
                    }
                ]
            },
        )
        transport, api, event_service, sleep = OandaTransportTestFactory().build(
            responses=[SimpleNamespace(status=400, body={"errorMessage": "duplicate client id"})],
            transaction_response=transaction_response,
        )
        api.order.get.return_value = self._filled_order_response(trade_id=None)

        response = transport.execute_order(
            {"instrument": "EUR_USD", "clientExtensions": {"id": "cid-1"}}
        )

        assert response.orderFillTransaction["id"] == "200"
        assert response.orderFillTransaction["price"] == "1.1010"
        assert response.orderFillTransaction["tradeOpened"]["tradeID"] == "T200"
        api.transaction.list.assert_called_once_with(
            "acct-1",
            pageSize=100,
            type="ORDER_FILL",
        )
        sleep.assert_not_called()
        event_service.log_trading_event.assert_not_called()

    def _filled_order_response(self, *, trade_id: str | None):
        order = {
            "id": "100",
            "type": "MARKET",
            "state": "FILLED",
            "createTime": "2026-05-08T00:00:00Z",
            "filledTime": "2026-05-08T00:00:01Z",
            "price": "1.1000",
        }
        if trade_id is not None:
            order["tradeOpenedID"] = trade_id
        return SimpleNamespace(status=200, body={"order": order})
