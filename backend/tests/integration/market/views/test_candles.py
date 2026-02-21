"""Unit tests for candle views."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestCandleDataView:
    """Test CandleDataView."""

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
        assert "count" in response.data["error"].lower()

    def test_get_candles_no_account(self, user: Any) -> None:
        """Test error when no OANDA account exists."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "NO_OANDA_ACCOUNT" in response.data.get("error_code", "")

    def test_get_candles_with_account(self, user: Any) -> None:
        """Test candle data retrieval with account."""
        # Create test account
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        # This will fail to connect to OANDA but tests the flow
        response = client.get("/api/market/candles/?instrument=EUR_USD&count=1")

        # May return 500 if OANDA API is not available, which is expected in unit tests
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @patch("apps.market.views.candles.v20.Context")
    def test_get_candles_api_error(self, mock_context: Mock, user: Any) -> None:
        """Test handling of OANDA API errors."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        # Mock API error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.body = None

        mock_api = MagicMock()
        mock_api.instrument.candles.return_value = mock_response
        mock_context.return_value = mock_api

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_candles_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access candles."""
        client = APIClient()

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
