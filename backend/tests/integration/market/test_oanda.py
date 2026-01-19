"""Integration tests for OANDA accounts API."""

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.enums import ApiType, Jurisdiction

if TYPE_CHECKING:
    from apps.accounts.models import User as UserType
else:
    UserType = Any

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db: Any) -> Any:
    """Create test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        email="test@example.com",
        password="testpass123",
        username="testuser",
    )


@pytest.mark.django_db
class TestOandaAccountsAPIIntegration:
    """Integration tests for OANDA accounts API endpoints."""

    def test_full_account_lifecycle(self, api_client: APIClient, user: Any) -> None:
        """Test complete account lifecycle: create, list, update, delete."""
        api_client.force_authenticate(user=user)

        # 1. Create account
        create_data = {
            "account_id": "101-001-1234567-001",
            "api_token": "test_token_12345",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": Jurisdiction.OTHER,
        }

        create_response = api_client.post("/api/market/accounts/", create_data, format="json")

        assert create_response.status_code == status.HTTP_201_CREATED
        account_id = create_response.data["id"]

        # 2. List accounts
        list_response = api_client.get("/api/market/accounts/")

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["count"] == 1

        # 3. Get account detail
        detail_response = api_client.get(f"/api/market/accounts/{account_id}/")

        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["account_id"] == "101-001-1234567-001"

        # 4. Update account
        update_data = {"is_active": False}

        update_response = api_client.put(
            f"/api/market/accounts/{account_id}/", update_data, format="json"
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data["is_active"] is False

        # 5. Delete account
        delete_response = api_client.delete(f"/api/market/accounts/{account_id}/")

        assert delete_response.status_code == status.HTTP_200_OK

        # 6. Verify deletion
        verify_response = api_client.get(f"/api/market/accounts/{account_id}/")

        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    def test_multiple_accounts_management(self, api_client: APIClient, user: Any) -> None:
        """Test managing multiple accounts."""
        api_client.force_authenticate(user=user)

        # Create multiple accounts
        for i in range(3):
            data = {
                "account_id": f"101-001-1234567-00{i}",
                "api_token": f"test_token_{i}",
                "api_type": ApiType.PRACTICE,
                "jurisdiction": Jurisdiction.OTHER,
            }

            response = api_client.post("/api/market/accounts/", data, format="json")
            assert response.status_code == status.HTTP_201_CREATED

        # List all accounts
        list_response = api_client.get("/api/market/accounts/")

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["count"] == 3

    def test_account_isolation_between_users(
        self, api_client: APIClient, user: Any, db: Any
    ) -> None:
        """Test that users can only access their own accounts."""
        # Create account for user1
        api_client.force_authenticate(user=user)

        data = {
            "account_id": "101-001-1234567-100",
            "api_token": "test_token",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": Jurisdiction.OTHER,
        }

        response = api_client.post("/api/market/accounts/", data, format="json")
        account_id = response.data["id"]

        # Create another user
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            email="user2@example.com",
            password="testpass123",
            username="user2",
        )

        # Try to access user1's account as user2
        api_client.force_authenticate(user=user2)

        response = api_client.get(f"/api/market/accounts/{account_id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
