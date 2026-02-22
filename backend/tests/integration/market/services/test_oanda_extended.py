"""Extended integration tests for OandaService."""

from decimal import Decimal
from typing import Any

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.services.oanda import (
    LimitOrderRequest,
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    OrderDirection,
    StopOrderRequest,
)


@pytest.mark.django_db
class TestOandaServiceExtendedIntegration:
    """Extended integration tests for OandaService."""

    def test_get_account_resource_with_invalid_token(self, user: Any) -> None:
        """Test getting account resource with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_account_resource()

    def test_get_open_positions_with_invalid_token(self, user: Any) -> None:
        """Test getting open positions with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_open_positions()

    def test_get_open_trades_with_invalid_token(self, user: Any) -> None:
        """Test getting open trades with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_open_trades()

    def test_get_pending_orders_with_invalid_token(self, user: Any) -> None:
        """Test getting pending orders with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-004",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_pending_orders()

    def test_get_order_history_with_invalid_token(self, user: Any) -> None:
        """Test getting order history with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-005",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_order_history()

    def test_get_order_with_invalid_token(self, user: Any) -> None:
        """Test getting specific order with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-006",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        with pytest.raises(OandaAPIError):
            service.get_order("123")

    def test_create_market_order_with_invalid_token(self, user: Any) -> None:
        """Test creating market order with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-007",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        request = MarketOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
        )

        with pytest.raises(OandaAPIError):
            service.create_market_order(request)

    def test_create_limit_order_with_invalid_token(self, user: Any) -> None:
        """Test creating limit order with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-008",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        request = LimitOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
            price=Decimal("1.10000"),
        )

        with pytest.raises(OandaAPIError):
            service.create_limit_order(request)

    def test_create_stop_order_with_invalid_token(self, user: Any) -> None:
        """Test creating stop order with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-009",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        request = StopOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
            price=Decimal("1.09000"),
        )

        with pytest.raises(OandaAPIError):
            service.create_stop_order(request)

    def test_order_direction_enum(self) -> None:
        """Test OrderDirection enum."""
        assert OrderDirection.LONG == "long"
        assert OrderDirection.SHORT == "short"

    def test_market_order_request_structure(self) -> None:
        """Test MarketOrderRequest dataclass."""
        request = MarketOrderRequest(
            instrument="GBP_USD",
            units=Decimal("500"),
            take_profit=Decimal("1.30000"),
            stop_loss=Decimal("1.28000"),
        )

        assert request.instrument == "GBP_USD"
        assert request.units == Decimal("500")
        assert request.take_profit == Decimal("1.30000")
        assert request.stop_loss == Decimal("1.28000")

    def test_limit_order_request_structure(self) -> None:
        """Test LimitOrderRequest dataclass."""
        request = LimitOrderRequest(
            instrument="USD_JPY",
            units=Decimal("1000"),
            price=Decimal("110.000"),
        )

        assert request.instrument == "USD_JPY"
        assert request.units == Decimal("1000")
        assert request.price == Decimal("110.000")

    def test_stop_order_request_structure(self) -> None:
        """Test StopOrderRequest dataclass."""
        request = StopOrderRequest(
            instrument="AUD_USD",
            units=Decimal("750"),
            price=Decimal("0.70000"),
        )

        assert request.instrument == "AUD_USD"
        assert request.units == Decimal("750")
        assert request.price == Decimal("0.70000")
