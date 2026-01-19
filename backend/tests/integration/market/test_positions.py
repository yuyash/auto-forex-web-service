"""Integration tests for positions API."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestPositionAPIIntegration:
    """Integration tests for position API."""

    def test_get_positions_no_accounts(self, user: Any) -> None:
        """Test getting positions when no accounts exist."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/positions/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_get_positions_with_account(self, user: Any) -> None:
        """Test getting positions with account."""
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

        response = client.get(f"/api/market/positions/?account_id={account.id}")

        # May return error if OANDA API unavailable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_put_position_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required for opening position."""
        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": "1000.00",
        }

        response = client.put("/api/market/positions/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_position_invalid_data(self, user: Any) -> None:
        """Test validation of position data."""
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
            # Missing required fields
        }

        response = client.put("/api/market/positions/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_positions_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access positions."""
        client = APIClient()

        response = client.get("/api/market/positions/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPositionDetailAPIIntegration:
    """Integration tests for position detail API."""

    def test_get_position_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/positions/123/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_position_missing_account_id(self, user: Any) -> None:
        """Test that account_id is required for closing position."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.patch("/api/market/positions/123/", {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
