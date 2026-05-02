"""Unit tests for position views."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.services.broker_order_guard import BrokerOrderGuardError
from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.oanda import OandaAPIError


def _guarded_oanda_error(message: str) -> OandaAPIError:
    try:
        raise OandaAPIError(message) from BrokerOrderGuardError(message)
    except OandaAPIError as exc:
        return exc


@pytest.mark.django_db
class TestPositionView:
    """Test PositionView."""

    @patch("apps.market.views.positions.OandaService")
    def test_get_positions_success(self, mock_service: Any, user: Any) -> None:
        """Test successful position retrieval."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        # Mock open trades
        mock_trade = MagicMock()
        mock_trade.trade_id = "123"
        mock_trade.instrument = "EUR_USD"
        mock_trade.direction.value = "long"
        mock_trade.units = Decimal("1000")
        mock_trade.entry_price = Decimal("1.10000")
        mock_trade.unrealized_pnl = Decimal("10.50")
        mock_trade.open_time = None
        mock_trade.close_time = None
        mock_trade.realized_pnl = None
        mock_trade.state = "OPEN"

        mock_service_instance = MagicMock()
        mock_service_instance.get_open_trades.return_value = [mock_trade]
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/positions/?account_id={account.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["instrument"] == "EUR_USD"

    @patch("apps.market.views.positions.OandaService")
    def test_get_positions_all_includes_closed(self, mock_service: Any, user: Any) -> None:
        """Test all-position retrieval includes closed trades."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        mock_trade = MagicMock()
        mock_trade.trade_id = "124"
        mock_trade.instrument = "USD_JPY"
        mock_trade.direction.value = "short"
        mock_trade.units = Decimal("1000")
        mock_trade.entry_price = Decimal("159.552")
        mock_trade.unrealized_pnl = Decimal("0")
        mock_trade.realized_pnl = Decimal("155")
        mock_trade.open_time = None
        mock_trade.close_time = None
        mock_trade.state = "CLOSED"

        mock_service_instance = MagicMock()
        mock_service_instance.get_trades.return_value = [mock_trade]
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/positions/?account_id={account.id}&status=all")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "closed"

    def test_get_positions_no_accounts(self, user: Any) -> None:
        """Test getting positions when no accounts exist."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/positions/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    @patch("apps.market.views.positions.OandaService")
    def test_put_position_success(self, mock_service: Any, user: Any) -> None:
        """Test opening a position."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        # Mock order result
        mock_result = MagicMock()
        mock_result.order_id = "456"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.10000")
        mock_result.state.value = "FILLED"
        mock_result.create_time = None

        mock_service_instance = MagicMock()
        mock_service_instance.create_market_order.return_value = mock_result
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "account_id": account.id,
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000.00",
        }

        response = client.put("/api/market/positions/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["instrument"] == "EUR_USD"

    def test_put_position_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000.00",
        }

        response = client.put("/api/market/positions/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.views.positions.OandaService")
    def test_put_position_guard_failure_returns_400(self, mock_service: Any, user: Any) -> None:
        """Guardrail denials should be clear client errors, not generic 500s."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-004",
            api_type=ApiType.PRACTICE,
        )
        mock_service.return_value.create_market_order.side_effect = _guarded_oanda_error(
            "Instrument USD_JPY is not enabled for broker order submission"
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.put(
            "/api/market/positions/",
            {
                "account_id": account.id,
                "instrument": "USD_JPY",
                "direction": "long",
                "units": "1000.00",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "ORDER_GUARD_VIOLATION"
        assert "Instrument USD_JPY" in response.data["error"]

    @patch("apps.market.views.positions.OandaService")
    def test_put_position_compliance_failure_returns_422(
        self, mock_service: Any, user: Any
    ) -> None:
        """Compliance denials should be surfaced as unprocessable orders."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-005",
            api_type=ApiType.PRACTICE,
        )
        mock_service.return_value.create_market_order.side_effect = ComplianceViolationError(
            "Order exceeds maximum leverage limit"
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.put(
            "/api/market/positions/",
            {
                "account_id": account.id,
                "instrument": "EUR_USD",
                "direction": "long",
                "units": "1000.00",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.data["error_code"] == "ORDER_COMPLIANCE_VIOLATION"
        assert "maximum leverage" in response.data["error"]


@pytest.mark.django_db
class TestPositionDetailView:
    """Test PositionDetailView."""

    def test_get_position_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/positions/123/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.views.positions.OandaService")
    def test_patch_position_close_success(self, mock_service: Any, user: Any) -> None:
        """Test closing a position."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )

        # Mock trade and close result
        mock_trade = MagicMock()
        mock_trade.trade_id = "789"

        mock_result = MagicMock()
        mock_result.order_id = "999"
        mock_result.instrument = "EUR_USD"
        mock_result.order_type.value = "MARKET"
        mock_result.direction.value = "short"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.10050")
        mock_result.state.value = "FILLED"
        mock_result.fill_time = None

        mock_service_instance = MagicMock()
        mock_service_instance.get_open_trades.return_value = [mock_trade]
        mock_service_instance.close_trade.return_value = mock_result
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        data = {"account_id": account.id}

        response = client.patch("/api/market/positions/789/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    @patch("apps.market.views.positions.OandaService")
    def test_patch_position_guard_failure_returns_400(self, mock_service: Any, user: Any) -> None:
        """Close-order guardrail denials should be clear client errors."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-006",
            api_type=ApiType.PRACTICE,
        )
        mock_trade = MagicMock()
        mock_trade.trade_id = "789"
        mock_service_instance = MagicMock()
        mock_service_instance.get_open_trades.return_value = [mock_trade]
        mock_service_instance.close_trade.side_effect = _guarded_oanda_error(
            "Live OANDA accounts are disabled"
        )
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.patch(
            "/api/market/positions/789/",
            {"account_id": account.id},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "ORDER_GUARD_VIOLATION"
        assert "Live OANDA accounts are disabled" in response.data["error"]

    @patch("apps.market.views.positions.OandaService")
    def test_patch_position_upstream_failure_returns_502(
        self, mock_service: Any, user: Any
    ) -> None:
        """Raw OANDA close failures should stay generic."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-007",
            api_type=ApiType.PRACTICE,
        )
        mock_trade = MagicMock()
        mock_trade.trade_id = "789"
        mock_service_instance = MagicMock()
        mock_service_instance.get_open_trades.return_value = [mock_trade]
        mock_service_instance.close_trade.side_effect = OandaAPIError("upstream rejected")
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.patch(
            "/api/market/positions/789/",
            {"account_id": account.id},
            format="json",
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.data == {
            "error": "Failed to close position",
            "error_code": "OANDA_UPSTREAM_ERROR",
        }
