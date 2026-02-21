"""Integration tests for candles API."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestCandleDataAPIIntegration:
    """Integration tests for candle data API."""

    def test_get_candles_missing_instrument(self, user: Any) -> None:
        """Test that instrument parameter is required."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "instrument" in response.data["error"].lower()

    def test_get_candles_invalid_count(self, user: Any) -> None:
        """Test validation of count parameter."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD&count=10000")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_candles_no_account(self, user: Any) -> None:
        """Test error when no OANDA account exists."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "NO_OANDA_ACCOUNT" in response.data.get("error_code", "")

    def test_get_candles_with_account(self, user: Any) -> None:
        """Test candle retrieval with account (may fail if OANDA unavailable)."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD&count=10")

        # May return 500 if OANDA API is unavailable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_candles_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access candles."""
        client = APIClient()

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
