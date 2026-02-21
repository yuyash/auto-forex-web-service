"""Unit tests for OANDA account views."""

from typing import Any


import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountView:
    """Test OandaAccountView."""

    def test_list_accounts_authenticated(self, user: Any) -> None:
        """Test listing accounts for authenticated user."""
        # Create test accounts
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/accounts/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_list_accounts_unauthenticated(self) -> None:
        """Test listing accounts without authentication."""
        client = APIClient()
        response = client.get("/api/market/accounts/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_account(self, user: Any) -> None:
        """Test creating a new OANDA account."""
        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "account_id": "101-001-1234567-003",
            "api_token": "test_token_12345",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": "OTHER",
        }

        response = client.post("/api/market/accounts/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["account_id"] == "101-001-1234567-003"

        # Verify account was created
        account = OandaAccounts.objects.get(account_id="101-001-1234567-003")
        assert account.user == user

    def test_create_account_invalid_data(self, user: Any) -> None:
        """Test creating account with invalid data."""
        client = APIClient()
        client.force_authenticate(user=user)

        data = {
            "account_id": "101-001-1234567-004",
            # Missing required api_token
            "api_type": ApiType.PRACTICE,
        }

        response = client.post("/api/market/accounts/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestOandaAccountDetailView:
    """Test OandaAccountDetailView."""

    def test_get_account_detail(self, user: Any) -> None:
        """Test retrieving account details."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-005",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["account_id"] == "101-001-1234567-005"

    def test_get_account_not_found(self, user: Any) -> None:
        """Test retrieving non-existent account."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/accounts/99999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_account(self, user: Any) -> None:
        """Test updating account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-006",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        data = {"is_active": False}

        response = client.put(f"/api/market/accounts/{account.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        # Verify update
        account.refresh_from_db()
        assert account.is_active is False

    def test_delete_account(self, user: Any) -> None:
        """Test deleting account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-007",
            api_type=ApiType.PRACTICE,
            is_used=False,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_200_OK

        # Verify deletion
        assert not OandaAccounts.objects.filter(id=account.id).exists()

    def test_delete_account_in_use(self, user: Any) -> None:
        """Test deleting account that is in use."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-008",
            api_type=ApiType.PRACTICE,
            is_used=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "in use" in response.data["error"].lower()

        # Verify account still exists
        assert OandaAccounts.objects.filter(id=account.id).exists()

    def test_access_other_user_account(self, user: Any, another_user: Any) -> None:
        """Test that users cannot access other users' accounts."""
        account = OandaAccounts.objects.create(
            user=another_user,
            account_id="101-001-1234567-009",
            api_type=ApiType.PRACTICE,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
