"""Unit tests for OANDA transport retry behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.market.services.oanda import OandaAPIError
from apps.market.services.oanda_transport import OandaOrderTransport


def _transport(*, responses):
    api = SimpleNamespace(order=SimpleNamespace(create=MagicMock(side_effect=responses)))
    account = SimpleNamespace(account_id="acct-1", user=SimpleNamespace(id=1))
    event_service = SimpleNamespace(log_trading_event=MagicMock())
    sleep = MagicMock()
    transport = OandaOrderTransport(
        api=api,
        account=account,
        event_service=event_service,
        logger=SimpleNamespace(warning=MagicMock(), error=MagicMock()),
        max_retries=3,
        retry_delay=0,
        max_retry_delay=1,
        error_class=OandaAPIError,
        sleep_func=sleep,
        randbelow_func=MagicMock(return_value=0),
    )
    return transport, api, event_service, sleep


def test_execute_order_retries_retryable_status_then_succeeds():
    transport, api, event_service, sleep = _transport(
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


def test_execute_order_logs_failure_for_non_retryable_status():
    transport, api, event_service, sleep = _transport(
        responses=[SimpleNamespace(status=400, body={"errorMessage": "bad request"})]
    )

    with pytest.raises(OandaAPIError, match="Order submission failed"):
        transport.execute_order({"instrument": "BAD"})

    api.order.create.assert_called_once()
    sleep.assert_not_called()
    event_service.log_trading_event.assert_called_once()
