"""Unit tests for health views."""

from typing import Any


import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts

User = get_user_model()


@pytest.mark.django_db
class TestOandaApiHealthView:
    """Test OandaApiHealthView."""

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

    def test_unauthenticated_access(self) -> None:
        """Test that unauthenticated users cannot access health endpoint."""
        client = APIClient()

        response = client.get("/api/market/health/oanda/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
