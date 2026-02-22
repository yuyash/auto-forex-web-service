"""Integration tests for candles API."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

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

    @patch("apps.market.views.candles.v20.Context")
    def test_get_candles_with_account(self, mock_context: Mock, user: Any) -> None:
        """Test candle retrieval with account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )
        account.set_api_token("test_token_12345")
        account.save()

        mock_candle = MagicMock()
        mock_candle.complete = True
        mock_candle.time = "2024-01-01T00:00:00.000000000Z"
        mock_candle.volume = 100
        mock_candle.mid.o = "1.10000"
        mock_candle.mid.h = "1.10100"
        mock_candle.mid.l = "1.09900"
        mock_candle.mid.c = "1.10050"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"candles": [mock_candle]}

        mock_api = MagicMock()
        mock_api.instrument.candles.return_value = mock_response
        mock_context.return_value = mock_api

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/?instrument=EUR_USD&count=10")

        assert response.status_code == status.HTTP_200_OK

    def test_get_candles_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access candles."""
        client = APIClient()

        response = client.get("/api/market/candles/?instrument=EUR_USD")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
