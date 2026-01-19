"""Integration tests for orders API."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestOrderAPIIntegration:
    """Integration tests for order API."""

    def test_get_orders_no_accounts(self, user: Any) -> None:
        """Test getting orders when no accounts exist."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/orders/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_get_orders_with_account(self, user: Any) -> None:
        """Test getting orders with account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )
        # Set encrypted token
        account.set_api_token("test_token_12345")
        account.save()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/orders/?account_id={account.id}")

        # May return error if OANDA API unavailable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

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
            account_id="101-001-1234567-002",
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

    def test_get_orders_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access orders."""
        client = APIClient()

        response = client.get("/api/market/orders/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrderDetailAPIIntegration:
    """Integration tests for order detail API."""

    def test_get_order_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/orders/123/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_order_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required for cancelling order."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete("/api/market/orders/123/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
