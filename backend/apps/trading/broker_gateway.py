"""Broker gateway abstractions for trading order execution."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from apps.market.services.oanda import (
    MarketOrder as OandaMarketOrder,
    MarketOrderRequest,
    OandaService,
    OpenTrade,
    Position as OandaPosition,
)


class BrokerGateway(Protocol):
    """Interface OrderService needs from a broker integration."""

    def create_market_order(
        self,
        request: MarketOrderRequest,
        *,
        override_price: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Create a broker market order."""

    def close_trade(
        self,
        *,
        trade: OpenTrade,
        units: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Close an individual broker trade."""

    def close_position(
        self,
        *,
        position: OandaPosition,
        units: Decimal | None = None,
        override_price: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Close broker exposure by instrument position."""


class OandaBrokerGateway:
    """Broker gateway backed by OandaService."""

    def __init__(self, service: OandaService) -> None:
        """Bind a concrete OANDA service implementation."""
        self.service = service

    def create_market_order(
        self,
        request: MarketOrderRequest,
        *,
        override_price: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Create a broker market order."""
        return self.service.create_market_order(request, override_price=override_price)

    def close_trade(
        self,
        *,
        trade: OpenTrade,
        units: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Close an individual broker trade."""
        return self.service.close_trade(trade=trade, units=units)

    def close_position(
        self,
        *,
        position: OandaPosition,
        units: Decimal | None = None,
        override_price: Decimal | None = None,
    ) -> OandaMarketOrder:
        """Close broker exposure by instrument position."""
        return self.service.close_position(
            position=position,
            units=units,
            override_price=override_price,
        )
