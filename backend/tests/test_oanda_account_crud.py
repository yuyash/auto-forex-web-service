"""
Unit tests for OANDA account CRUD API endpoints.

Tests cover:
- Listing user's accounts
- Adding new account with valid data
- Account detail retrieval
- Account update
- Account deletion
- Cross-user account access prevention

Requirements: 4.1, 4.5
"""

from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import OandaAccount, User


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def user(db) -> User:  # pylint: disable=unused-argument
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def other_user(db) -> User:  # pylint: disable=unused-argument
    """Create another test user for cross-user access tests."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )


@pytest.fixture
def oanda_account(user: User) -> OandaAccount:
    """Create a test OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        currency="USD",
    )
    account.set_api_token("test_token_12345")
    account.save()
    return account


@pytest.mark.django_db
class TestOandaAccountListView:
    """Test cases for listing OANDA accounts."""

    def test_list_accounts_authenticated(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test listing accounts for authenticated user."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["account_id"] == "001-001-1234567-001"
        assert response.data[0]["api_type"] == "practice"
        assert "api_token" not in response.data[0]  # Should not expose token

    def test_list_accounts_unauthenticated(self, api_client: APIClient) -> None:
        """Test listing accounts without authentication."""
        url = reverse("accounts:oanda_accounts_list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_accounts_empty(self, api_client: APIClient, user: User) -> None:
        """Test listing accounts when user has no accounts."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_list_accounts_multiple(self, api_client: APIClient, user: User) -> None:
        """Test listing multiple accounts."""
        # Create multiple accounts
        account1 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        account2 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type="live",
        )
        account2.set_api_token("token2")
        account2.save()

        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_list_accounts_only_own_accounts(
        self, api_client: APIClient, user: User, other_user: User
    ) -> None:
        """Test that users only see their own accounts."""
        # Create account for user
        account1 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        # Create account for other_user
        account2 = OandaAccount.objects.create(
            user=other_user,
            account_id="001-001-1234567-002",
            api_type="practice",
        )
        account2.set_api_token("token2")
        account2.save()

        # Authenticate as user and list accounts
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["account_id"] == "001-001-1234567-001"


@pytest.mark.django_db
class TestOandaAccountCreateView:
    """Test cases for creating OANDA accounts."""

    def test_create_account_valid_data(self, api_client: APIClient, user: User) -> None:
        """Test creating account with valid data."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        data = {
            "account_id": "001-001-1234567-001",
            "api_token": "test_api_token_12345",
            "api_type": "practice",
            "currency": "USD",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["account_id"] == "001-001-1234567-001"
        assert response.data["api_type"] == "practice"
        assert response.data["currency"] == "USD"
        assert "api_token" not in response.data  # Should not expose token

        # Verify account was created in database
        account = OandaAccount.objects.get(user=user, account_id="001-001-1234567-001")
        assert account is not None
        assert account.get_api_token() == "test_api_token_12345"

    def test_create_account_unauthenticated(self, api_client: APIClient) -> None:
        """Test creating account without authentication."""
        url = reverse("accounts:oanda_accounts_list")

        data = {
            "account_id": "001-001-1234567-001",
            "api_token": "test_token",
            "api_type": "practice",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_account_duplicate_account_id(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test creating account with duplicate account_id for same user."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        data = {
            "account_id": "001-001-1234567-001",  # Same as existing account
            "api_token": "new_token",
            "api_type": "live",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "account_id" in response.data

    def test_create_account_missing_required_fields(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating account with missing required fields."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        data = {
            "account_id": "001-001-1234567-001",
            # Missing api_token
            "api_type": "practice",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "api_token" in response.data

    def test_create_account_invalid_api_type(self, api_client: APIClient, user: User) -> None:
        """Test creating account with invalid api_type."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_accounts_list")

        data = {
            "account_id": "001-001-1234567-001",
            "api_token": "test_token",
            "api_type": "invalid",  # Invalid type
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestOandaAccountDetailView:
    """Test cases for retrieving account details."""

    def test_get_account_detail(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test retrieving account details."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["account_id"] == "001-001-1234567-001"
        assert response.data["api_type"] == "practice"
        assert "api_token" not in response.data

    def test_get_account_detail_unauthenticated(
        self, api_client: APIClient, oanda_account: OandaAccount
    ) -> None:
        """Test retrieving account details without authentication."""
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_account_detail_not_found(self, api_client: APIClient, user: User) -> None:
        """Test retrieving non-existent account."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": 99999})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_account_detail_cross_user_access(
        self, api_client: APIClient, user: User, other_user: User
    ) -> None:
        """Test that users cannot access other users' accounts."""
        # Create account for other_user
        other_account = OandaAccount.objects.create(
            user=other_user,
            account_id="001-001-1234567-002",
            api_type="practice",
        )
        other_account.set_api_token("other_token")
        other_account.save()

        # Try to access other_user's account as user
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": other_account.id})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOandaAccountUpdateView:
    """Test cases for updating OANDA accounts."""

    def test_update_account(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test updating account."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        data = {
            "api_type": "live",
            "currency": "EUR",
        }

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["api_type"] == "live"
        assert response.data["currency"] == "EUR"

        # Verify changes in database
        oanda_account.refresh_from_db()
        assert oanda_account.api_type == "live"
        assert oanda_account.currency == "EUR"

    def test_update_account_api_token(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test updating API token."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        data = {
            "api_token": "new_token_67890",
        }

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify token was updated
        oanda_account.refresh_from_db()
        assert oanda_account.get_api_token() == "new_token_67890"

    def test_update_account_unauthenticated(
        self, api_client: APIClient, oanda_account: OandaAccount
    ) -> None:
        """Test updating account without authentication."""
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        data = {"api_type": "live"}

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_account_not_found(self, api_client: APIClient, user: User) -> None:
        """Test updating non-existent account."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": 99999})

        data = {"api_type": "live"}

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_account_cross_user_access(
        self, api_client: APIClient, user: User, other_user: User
    ) -> None:
        """Test that users cannot update other users' accounts."""
        # Create account for other_user
        other_account = OandaAccount.objects.create(
            user=other_user,
            account_id="001-001-1234567-002",
            api_type="practice",
        )
        other_account.set_api_token("other_token")
        other_account.save()

        # Try to update other_user's account as user
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": other_account.id})

        data = {"api_type": "live"}

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Verify account was not updated
        other_account.refresh_from_db()
        assert other_account.api_type == "practice"


@pytest.mark.django_db
class TestOandaAccountDeleteView:
    """Test cases for deleting OANDA accounts."""

    def test_delete_account(
        self, api_client: APIClient, user: User, oanda_account: OandaAccount
    ) -> None:
        """Test deleting account."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

        # Verify account was deleted
        assert not OandaAccount.objects.filter(id=oanda_account.id).exists()

    def test_delete_account_unauthenticated(
        self, api_client: APIClient, oanda_account: OandaAccount
    ) -> None:
        """Test deleting account without authentication."""
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": oanda_account.id})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Verify account was not deleted
        assert OandaAccount.objects.filter(id=oanda_account.id).exists()

    def test_delete_account_not_found(self, api_client: APIClient, user: User) -> None:
        """Test deleting non-existent account."""
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": 99999})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_account_cross_user_access(
        self, api_client: APIClient, user: User, other_user: User
    ) -> None:
        """Test that users cannot delete other users' accounts."""
        # Create account for other_user
        other_account = OandaAccount.objects.create(
            user=other_user,
            account_id="001-001-1234567-002",
            api_type="practice",
        )
        other_account.set_api_token("other_token")
        other_account.save()

        # Try to delete other_user's account as user
        api_client.force_authenticate(user=user)
        url = reverse("accounts:oanda_account_detail", kwargs={"account_id": other_account.id})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Verify account was not deleted
        assert OandaAccount.objects.filter(id=other_account.id).exists()
