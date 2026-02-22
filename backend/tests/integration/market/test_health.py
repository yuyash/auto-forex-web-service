"""Integration tests for health API."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts


@pytest.mark.django_db
class TestOandaApiHealthAPIIntegration:
    """Integration tests for OANDA API health check."""

    def test_get_health_no_account(self, user: Any) -> None:
        """Test getting health status when no account exists."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "NO_OANDA_ACCOUNT" in response.data["error_code"]

    def test_get_health_no_status_yet(self, user: Any) -> None:
        """Test getting health status when no check has been performed."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is None

    def test_post_health_check_no_account(self, user: Any) -> None:
        """Test performing health check when no account exists."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.services.health.v20.Context")
    def test_post_health_check_with_account(self, mock_context: Mock, user: Any) -> None:
        """Test performing health check with account."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_api = MagicMock()
        mock_api.account.get.return_value = mock_response
        mock_context.return_value = mock_api

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_200_OK

    def test_health_check_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access health endpoint."""
        client = APIClient()

        response = client.get("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
