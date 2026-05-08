"""Unit tests for broker gateway collaborators."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from apps.market.services.oanda import MarketOrderRequest
from apps.trading.broker_gateway import OandaBrokerGateway


class TestOandaBrokerGateway:
    """Tests for the OANDA broker gateway adapter."""

    def test_create_market_order_delegates_to_oanda_service(self):
        service = MagicMock()
        request = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
        service.create_market_order.return_value = MagicMock(order_id="order-1")
        gateway = OandaBrokerGateway(service)

        result = gateway.create_market_order(request, override_price=Decimal("1.1000"))

        assert result is service.create_market_order.return_value
        service.create_market_order.assert_called_once_with(
            request,
            override_price=Decimal("1.1000"),
        )

    def test_close_trade_delegates_to_oanda_service(self):
        service = MagicMock()
        trade = MagicMock()
        service.close_trade.return_value = MagicMock(order_id="close-trade")
        gateway = OandaBrokerGateway(service)

        result = gateway.close_trade(trade=trade, units=Decimal("500"))

        assert result is service.close_trade.return_value
        service.close_trade.assert_called_once_with(trade=trade, units=Decimal("500"))

    def test_close_position_delegates_to_oanda_service(self):
        service = MagicMock()
        position = MagicMock()
        service.close_position.return_value = MagicMock(order_id="close-position")
        gateway = OandaBrokerGateway(service)

        result = gateway.close_position(
            position=position,
            units=Decimal("500"),
            override_price=Decimal("1.1100"),
        )

        assert result is service.close_position.return_value
        service.close_position.assert_called_once_with(
            position=position,
            units=Decimal("500"),
            override_price=Decimal("1.1100"),
        )
