"""Integration tests for OandaService."""

from decimal import Decimal
from typing import Any

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.services.oanda import (
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
)


@pytest.mark.django_db
class TestOandaServiceIntegration:
    """Integration tests for OandaService."""

    def test_oanda_service_initialization(self, user: Any) -> None:
        """Test OandaService initialization."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("test_token_12345")
        account.save()

        service = OandaService(account)

        assert service is not None
        assert service.account == account

    def test_get_account_details_with_invalid_token(self, user: Any) -> None:
        """Test getting account details with invalid token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("invalid_token")
        account.save()

        service = OandaService(account)

        # Should raise OandaAPIError with invalid token
        with pytest.raises(OandaAPIError):
            service.get_account_details()

    def test_create_market_order_request_structure(self) -> None:
        """Test MarketOrderRequest structure."""
        request = MarketOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
            take_profit=Decimal("1.10000"),
            stop_loss=Decimal("1.09000"),
        )

        assert request.instrument == "EUR_USD"
        assert request.units == Decimal("1000")
        assert request.take_profit == Decimal("1.10000")
        assert request.stop_loss == Decimal("1.09000")

    def test_make_jsonable_method(self, user: Any) -> None:
        """Test make_jsonable utility method."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("test_token")
        account.save()

        service = OandaService(account)

        # Test with simple object
        test_obj = {"key": "value", "number": 123}
        result = service.make_jsonable(test_obj)

        assert result == test_obj
