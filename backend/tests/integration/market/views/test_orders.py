"""Unit tests for order views."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestOrderView:
    """Test OrderView."""

    @patch("apps.market.views.orders.OandaService")
    def test_get_orders_success(self, mock_service: Any, user: Any) -> None:
        """Test successful order retrieval."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        # Mock pending orders
        mock_order = MagicMock()
        mock_order.order_id = "123"
        mock_order.instrument = "EUR_USD"
        mock_order.order_type.value = "LIMIT"
        mock_order.direction.value = "long"
        mock_order.units = Decimal("1000")
        mock_order.price = Decimal("1.09000")
        mock_order.state.value = "PENDING"
        mock_order.time_in_force = "GTC"
        mock_order.create_time = None
        mock_order.fill_time = None
        mock_order.cancel_time = None

        mock_service_instance = MagicMock()
        mock_service_instance.get_pending_orders.return_value = [mock_order]
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/orders/?account_id={account.id}&status=pending")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["instrument"] == "EUR_USD"

    def test_get_orders_no_accounts(self, user: Any) -> None:
        """Test getting orders when no accounts exist."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/orders/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    @patch("apps.market.views.orders.OandaService")
    def test_post_order_market_success(self, mock_service: Any, user: Any) -> None:
        """Test creating a market order."""
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
        mock_result.direction.value = "long"
        mock_result.units = Decimal("1000")
        mock_result.price = Decimal("1.10000")
        mock_result.state.value = "FILLED"
        mock_result.time_in_force = "FOK"
        mock_result.create_time = None
        mock_result.fill_time = None
        mock_result.cancel_time = None

        mock_service_instance = MagicMock()
        mock_service_instance.create_market_order.return_value = mock_result
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "account_id": account.id,
            "instrument": "EUR_USD",
            "order_type": "market",
            "direction": "long",
            "units": "1000.00",
        }

        response = client.post("/api/market/orders/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["instrument"] == "EUR_USD"

    def test_post_order_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "instrument": "EUR_USD",
            "order_type": "market",
            "direction": "long",
            "units": "1000.00",
        }

        response = client.post("/api/market/orders/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_post_order_invalid_data(self, user: Any) -> None:
        """Test validation of order data."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "account_id": account.id,
            "instrument": "EUR_USD",
            "order_type": "limit",
            "direction": "long",
            "units": "1000.00",
            # Missing required 'price' for limit order
        }

        response = client.post("/api/market/orders/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestOrderDetailView:
    """Test OrderDetailView."""

    def test_get_order_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/orders/123/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.views.orders.OandaService")
    def test_delete_order_success(self, mock_service: Any, user: Any) -> None:
        """Test cancelling an order."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-004",
            api_type=ApiType.PRACTICE,
        )

        # Mock order and cancel result
        mock_order = MagicMock()
        mock_order.order_id = "789"

        mock_result = MagicMock()
        mock_result.order_id = "789"
        mock_result.transaction_id = "999"
        mock_result.cancel_time = None
        mock_result.state.value = "CANCELLED"

        mock_service_instance = MagicMock()
        mock_service_instance.get_order.return_value = mock_order
        mock_service_instance.cancel_order.return_value = mock_result
        mock_service.return_value = mock_service_instance

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(f"/api/market/orders/789/?account_id={account.id}")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data
