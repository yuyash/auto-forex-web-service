"""
Integration tests for OANDA account API endpoints.

Tests account creation, retrieval, update, deletion, listing, and filtering.
"""

from decimal import Decimal

from django.urls import reverse

from apps.market.models import OandaAccounts
from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import OandaAccountFactory


class OandaAccountListCreateTests(APIIntegrationTestCase):
    """Tests for OANDA account list and create endpoints."""

    def test_create_account_success(self) -> None:
        """Test creating a new OANDA account with valid data."""
        url = reverse("market:oanda_accounts_list")
        data = {
            "account_id": "101-001-12345678-001",
            "api_token": "test-api-token-12345",
            "api_type": "practice",
            "jurisdiction": "OTHER",
            "currency": "USD",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        self.assertIn("id", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["account_id"], data["account_id"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["api_type"], data["api_type"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["currency"], data["currency"])  # ty:ignore[possibly-missing-attribute]

        # Verify account was created in database
        account = OandaAccounts.objects.get(id=response.data["id"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(account.user, self.user)
        self.assertEqual(account.account_id, data["account_id"])
        self.assertEqual(account.api_type, data["api_type"])
        # Verify API token was encrypted
        self.assertNotEqual(account.api_token, data["api_token"])
        self.assertEqual(
            account.get_api_token(),  # type: ignore[attr-defined]
            data["api_token"],
        )

    def test_create_account_sets_first_as_default(self) -> None:
        """Test that the first account created is automatically set as default."""
        url = reverse("market:oanda_accounts_list")
        data = {
            "account_id": "101-001-12345678-001",
            "api_token": "test-api-token-12345",
            "api_type": "practice",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        account = OandaAccounts.objects.get(id=response.data["id"])  # ty:ignore[possibly-missing-attribute]
        self.assertTrue(account.is_default)

    def test_create_account_duplicate_account_id_same_api_type(self) -> None:
        """Test that creating duplicate account_id with same api_type fails."""
        # Create first account
        OandaAccountFactory(
            user=self.user,
            account_id="101-001-12345678-001",
            api_type="practice",
        )

        # Try to create duplicate
        url = reverse("market:oanda_accounts_list")
        data = {
            "account_id": "101-001-12345678-001",
            "api_token": "test-api-token-12345",
            "api_type": "practice",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("account_id", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_create_account_allows_same_account_id_different_api_type(self) -> None:
        """Test that same account_id is allowed for different api_type."""
        # Create practice account
        OandaAccountFactory(
            user=self.user,
            account_id="101-001-12345678-001",
            api_type="practice",
        )

        # Create live account with same account_id
        url = reverse("market:oanda_accounts_list")
        data = {
            "account_id": "101-001-12345678-001",
            "api_token": "test-api-token-12345",
            "api_type": "live",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        self.assertEqual(response.data["account_id"], data["account_id"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["api_type"], "live")  # ty:ignore[possibly-missing-attribute]

    def test_create_account_missing_required_fields(self) -> None:
        """Test that creating account without required fields fails."""
        url = reverse("market:oanda_accounts_list")
        data = {
            "api_type": "practice",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("account_id", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("api_token", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_create_account_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot create accounts."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("market:oanda_accounts_list")
        data = {
            "account_id": "101-001-12345678-001",
            "api_token": "test-api-token-12345",
            "api_type": "practice",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]

    def test_list_accounts_success(self) -> None:
        """Test listing all accounts for authenticated user."""
        # Create multiple accounts
        accounts = OandaAccountFactory.create_batch(3, user=self.user)

        url = reverse("market:oanda_accounts_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("results", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["count"], 3)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 3)  # ty:ignore[possibly-missing-attribute]

        # Verify accounts are ordered by created_at descending
        result_ids = [acc["id"] for acc in response.data["results"]]  # ty:ignore[possibly-missing-attribute]
        expected_ids = [
            acc.id for acc in sorted(accounts, key=lambda a: a.created_at, reverse=True)
        ]
        self.assertEqual(result_ids, expected_ids)

    def test_list_accounts_empty(self) -> None:
        """Test listing accounts when user has no accounts."""
        url = reverse("market:oanda_accounts_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 0)  # ty:ignore[possibly-missing-attribute]

    def test_list_accounts_filters_by_user(self) -> None:
        """Test that listing only returns accounts belonging to the user."""
        # Create accounts for current user
        OandaAccountFactory.create_batch(2, user=self.user)

        # Create accounts for another user
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        OandaAccountFactory.create_batch(3, user=other_user)

        url = reverse("market:oanda_accounts_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 2)  # ty:ignore[possibly-missing-attribute]

    def test_list_accounts_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot list accounts."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("market:oanda_accounts_list")

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]


class OandaAccountDetailTests(APIIntegrationTestCase):
    """Tests for OANDA account detail, update, and delete endpoints."""

    def test_retrieve_account_success(self) -> None:
        """Test retrieving a specific account."""
        account = OandaAccountFactory(user=self.user)
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["id"], account.pk)  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        self.assertEqual(response.data["account_id"], account.account_id)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["api_type"], account.api_type)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["currency"], account.currency)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("balance", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("margin_used", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_retrieve_account_not_found(self) -> None:
        """Test retrieving non-existent account returns 404."""
        url = reverse("market:oanda_account_detail", kwargs={"account_id": 99999})

        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_retrieve_account_belongs_to_other_user(self) -> None:
        """Test that users cannot retrieve accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_update_account_success(self) -> None:
        """Test updating account fields."""
        account = OandaAccountFactory(
            user=self.user,
            currency="USD",
            is_active=True,
        )
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]
        data = {
            "currency": "EUR",
            "is_active": False,
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["currency"], "EUR")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["is_active"], False)  # ty:ignore[possibly-missing-attribute]

        # Verify changes persisted in database
        account.refresh_from_db()  # type: ignore[attr-defined]
        self.assertEqual(account.currency, "EUR")
        self.assertFalse(account.is_active)

    def test_update_account_api_token(self) -> None:
        """Test updating account API token."""
        account = OandaAccountFactory(user=self.user)
        old_token = account.get_api_token()  # type: ignore[attr-defined]
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]
        data = {
            "api_token": "new-api-token-67890",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]

        # Verify token was updated and encrypted
        account.refresh_from_db()  # type: ignore[attr-defined]
        new_token = account.get_api_token()  # type: ignore[attr-defined]
        self.assertNotEqual(new_token, old_token)
        self.assertEqual(new_token, "new-api-token-67890")

    def test_update_account_set_as_default(self) -> None:
        """Test setting an account as default."""
        # Create two accounts
        account1 = OandaAccountFactory(user=self.user, is_default=True)
        account2 = OandaAccountFactory(user=self.user, is_default=False)

        url = reverse("market:oanda_account_detail", kwargs={"account_id": account2.pk})  # ty:ignore[unresolved-attribute]
        data = {
            "is_default": True,
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]

        # Verify account2 is now default and account1 is not
        account1.refresh_from_db()  # type: ignore[attr-defined]
        account2.refresh_from_db()  # type: ignore[attr-defined]
        self.assertFalse(account1.is_default)
        self.assertTrue(account2.is_default)

    def test_update_account_not_found(self) -> None:
        """Test updating non-existent account returns 404."""
        url = reverse("market:oanda_account_detail", kwargs={"account_id": 99999})
        data = {"currency": "EUR"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_update_account_belongs_to_other_user(self) -> None:
        """Test that users cannot update accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]
        data = {"currency": "EUR"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_delete_account_success(self) -> None:
        """Test deleting an account."""
        account = OandaAccountFactory(user=self.user, is_used=False)
        account_id = account.pk  # type: ignore[attr-defined]
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.delete(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("message", response.data)  # ty:ignore[possibly-missing-attribute]

        # Verify account was deleted from database
        self.assertFalse(OandaAccounts.objects.filter(id=account_id).exists())

    def test_delete_account_in_use(self) -> None:
        """Test that accounts marked as in use cannot be deleted."""
        account = OandaAccountFactory(user=self.user, is_used=True)
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.delete(url)

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]

        # Verify account still exists
        self.assertTrue(
            OandaAccounts.objects.filter(id=account.pk)  # type: ignore[attr-defined]  # type: ignore[attr-defined].exists()  # type: ignore[attr-defined]
        )

    def test_delete_account_not_found(self) -> None:
        """Test deleting non-existent account returns 404."""
        url = reverse("market:oanda_account_detail", kwargs={"account_id": 99999})

        response = self.client.delete(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_delete_account_belongs_to_other_user(self) -> None:
        """Test that users cannot delete accounts belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        account = OandaAccountFactory(user=other_user)
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.delete(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

        # Verify account still exists
        self.assertTrue(
            OandaAccounts.objects.filter(id=account.pk)  # type: ignore[attr-defined]  # type: ignore[attr-defined].exists()  # type: ignore[attr-defined]
        )


class OandaAccountFilteringTests(APIIntegrationTestCase):
    """Tests for filtering and querying OANDA accounts."""

    def test_filter_accounts_by_api_type(self) -> None:
        """Test filtering accounts by API type."""
        # Create accounts with different API types
        OandaAccountFactory.create_batch(2, user=self.user, api_type="practice")
        OandaAccountFactory.create_batch(3, user=self.user, api_type="live")

        url = reverse("market:oanda_accounts_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 5)  # ty:ignore[possibly-missing-attribute]

        # Verify we can identify accounts by api_type
        practice_accounts = [
            acc for acc in response.data["results"] if acc["api_type"] == "practice"  # ty:ignore[possibly-missing-attribute]
        ]
        live_accounts = [acc for acc in response.data["results"] if acc["api_type"] == "live"]  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(practice_accounts), 2)
        self.assertEqual(len(live_accounts), 3)

    def test_filter_accounts_by_active_status(self) -> None:
        """Test filtering accounts by active status."""
        # Create active and inactive accounts
        OandaAccountFactory.create_batch(3, user=self.user, is_active=True)
        OandaAccountFactory.create_batch(2, user=self.user, is_active=False)

        url = reverse("market:oanda_accounts_list")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 5)  # ty:ignore[possibly-missing-attribute]

        # Verify we can identify accounts by is_active
        active_accounts = [acc for acc in response.data["results"] if acc["is_active"]]  # ty:ignore[possibly-missing-attribute]
        inactive_accounts = [acc for acc in response.data["results"] if not acc["is_active"]]  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(active_accounts), 3)
        self.assertEqual(len(inactive_accounts), 2)

    def test_accounts_include_balance_fields(self) -> None:
        """Test that account responses include balance and margin fields."""
        account = OandaAccountFactory(
            user=self.user,
            balance=Decimal("10000.00"),
            margin_used=Decimal("500.00"),
            margin_available=Decimal("9500.00"),
            unrealized_pnl=Decimal("150.50"),
        )
        url = reverse("market:oanda_account_detail", kwargs={"account_id": account.pk})  # ty:ignore[unresolved-attribute]

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("balance", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("margin_used", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("margin_available", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("unrealized_pnl", response.data)  # ty:ignore[possibly-missing-attribute]
