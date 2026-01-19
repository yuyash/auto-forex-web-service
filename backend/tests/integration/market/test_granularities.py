"""Integration tests for granularities API."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestSupportedGranularitiesAPIIntegration:
    """Integration tests for supported granularities API."""

    def test_get_granularities_standard_list(self, user: Any) -> None:
        """Test getting standard granularities list."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/granularities/")

        assert response.status_code == status.HTTP_200_OK
        assert "granularities" in response.data
        assert response.data["count"] > 0

        # Check some standard granularities
        granularities = [g["value"] for g in response.data["granularities"]]
        assert "M1" in granularities
        assert "H1" in granularities
        assert "D" in granularities

    def test_get_granularities_with_account(self, user: Any) -> None:
        """Test fetching granularities with active account."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/granularities/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["source"] in ["oanda", "standard"]

    def test_get_granularities_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access granularities."""
        client = APIClient()

        response = client.get("/api/market/candles/granularities/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
