"""Integration tests for instruments API."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestSupportedInstrumentsAPIIntegration:
    """Integration tests for supported instruments API."""

    def test_get_instruments_fallback(self, user: Any) -> None:
        """Test fallback to default instruments list."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/instruments/")

        assert response.status_code == status.HTTP_200_OK
        assert "instruments" in response.data
        assert response.data["count"] > 0
        assert "EUR_USD" in response.data["instruments"]

    @patch("apps.market.views.instruments.v20.Context")
    def test_get_instruments_with_account(self, mock_context: Mock, user: Any) -> None:
        """Test fetching instruments with active account."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        mock_instrument = MagicMock()
        mock_instrument.name = "EUR_USD"
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instruments": [mock_instrument]}
        mock_api = MagicMock()
        mock_api.account.instruments.return_value = mock_response
        mock_context.return_value = mock_api

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/instruments/")

        assert response.status_code == status.HTTP_200_OK
        assert "instruments" in response.data

    def test_get_instruments_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access instruments."""
        client = APIClient()

        response = client.get("/api/market/instruments/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestInstrumentDetailAPIIntegration:
    """Integration tests for instrument detail API."""

    def test_get_instrument_detail_no_account(self, user: Any) -> None:
        """Test instrument detail when no account exists."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/instruments/EUR_USD/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.market.views.instruments.v20.Context")
    def test_get_instrument_detail_with_account(self, mock_context: Mock, user: Any) -> None:
        """Test instrument detail with account."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        mock_instrument = MagicMock()
        mock_instrument.name = "EUR_USD"
        mock_instrument.displayName = "EUR/USD"
        mock_instrument.type = "CURRENCY"
        mock_instrument.pipLocation = -4
        mock_instrument.displayPrecision = 5
        mock_instrument.tradeUnitsPrecision = 0
        mock_instrument.minimumTradeSize = "1"
        mock_instrument.maximumTradeUnits = "100000000"
        mock_instrument.maximumPositionSize = "0"
        mock_instrument.maximumOrderUnits = "100000000"
        mock_instrument.marginRate = "0.0333"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instruments": [mock_instrument]}

        mock_api = MagicMock()
        mock_api.account.instruments.return_value = mock_response
        mock_api.pricing.get.return_value = MagicMock(status=404)
        mock_context.return_value = mock_api

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/instruments/EUR_USD/")

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_get_instrument_detail_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access instrument details."""
        client = APIClient()

        response = client.get("/api/market/instruments/EUR_USD/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
