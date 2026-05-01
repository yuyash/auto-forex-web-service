"""Unit tests for OANDA account views."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
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

    @patch("apps.market.services.accounts.OandaService")
    def test_list_accounts_uses_cached_snapshot(self, mock_oanda_service: Any, user: Any) -> None:
        """List responses should not fetch OANDA live data in the request path."""
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-011",
            api_type=ApiType.PRACTICE,
            balance=Decimal("12000"),
            margin_available=Decimal("11800"),
            snapshot_refreshed_at=timezone.now(),
            hedging_enabled=False,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/accounts/")

        assert response.status_code == status.HTTP_200_OK
        account = response.data["results"][0]
        assert account["balance"] == "12000.00"
        assert account["live_data"] is True
        assert account["snapshot_stale"] is False
        assert account["position_mode"] == "netting"
        mock_oanda_service.assert_not_called()

    def test_list_accounts_unauthenticated(self) -> None:
        """Test listing accounts without authentication."""
        client = APIClient()
        response = client.get("/api/market/accounts/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.market.models.oanda.invalidate_market_metadata_cache")
    def test_create_account(self, mock_invalidate: Any, user: Any) -> None:
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
        mock_invalidate.assert_called_once_with({account.api_hostname})

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

    @patch("apps.market.services.accounts.OandaService")
    def test_get_account_detail_uses_cached_snapshot(
        self, mock_oanda_service: Any, user: Any
    ) -> None:
        """Detail responses should read cached snapshot fields only."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-012",
            api_type=ApiType.PRACTICE,
            nav=Decimal("12100"),
            open_trade_count=2,
            snapshot_refreshed_at=timezone.now(),
            hedging_enabled=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["nav"] == "12100.00"
        assert response.data["open_trade_count"] == 2
        assert response.data["position_mode"] == "hedging"
        mock_oanda_service.assert_not_called()

    def test_get_account_not_found(self, user: Any) -> None:
        """Test retrieving non-existent account."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/accounts/99999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.market.models.oanda.invalidate_market_metadata_cache")
    def test_update_account(self, mock_invalidate: Any, user: Any) -> None:
        """Test updating account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-006",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )
        mock_invalidate.reset_mock()

        client = APIClient()
        client.force_authenticate(user=user)

        data = {"is_active": False}

        response = client.put(f"/api/market/accounts/{account.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        # Verify update
        account.refresh_from_db()
        assert account.is_active is False
        mock_invalidate.assert_called_once_with({account.api_hostname})

    @patch("apps.market.models.oanda.invalidate_market_metadata_cache")
    def test_delete_account(self, mock_invalidate: Any, user: Any) -> None:
        """Test deleting account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-007",
            api_type=ApiType.PRACTICE,
            is_used=False,
        )
        mock_invalidate.reset_mock()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(f"/api/market/accounts/{account.id}/")

        assert response.status_code == status.HTTP_200_OK

        # Verify deletion
        assert not OandaAccounts.objects.filter(id=account.id).exists()
        mock_invalidate.assert_called_once_with({account.api_hostname})

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


@pytest.mark.django_db
class TestOandaAccountSnapshotRefreshView:
    """Test OandaAccountSnapshotRefreshView."""

    @patch("apps.market.tasks.accounts.refresh_oanda_account_snapshots.apply_async")
    def test_post_queues_snapshot_refresh(self, mock_apply_async: Any, user: Any) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-013",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )
        mock_apply_async.return_value = MagicMock(id="task-123")

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/market/accounts/{account.id}/refresh/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["id"] == account.pk
        assert response.data["account_id"] == account.account_id
        assert response.data["task_id"]
        assert response.data["status"] == "queued"
        assert response.data["snapshot_stale"] is True
        mock_apply_async.assert_called_once_with(
            kwargs={"account_id": account.pk},
            queue="market",
            task_id=response.data["task_id"],
        )
        account.refresh_from_db()
        assert account.snapshot_refresh_task_id == response.data["task_id"]
        assert account.snapshot_refresh_status == OandaAccounts.SnapshotRefreshStatus.QUEUED

    @patch("apps.market.tasks.accounts.refresh_oanda_account_snapshots.apply_async")
    def test_post_rejects_inactive_account(self, mock_apply_async: Any, user: Any) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-014",
            api_type=ApiType.PRACTICE,
            is_active=False,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/market/accounts/{account.id}/refresh/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "inactive" in response.data["error"].lower()
        mock_apply_async.assert_not_called()

    @patch("apps.market.tasks.accounts.refresh_oanda_account_snapshots.apply_async")
    def test_post_does_not_queue_other_users_account(
        self, mock_apply_async: Any, user: Any, another_user: Any
    ) -> None:
        account = OandaAccounts.objects.create(
            user=another_user,
            account_id="101-001-1234567-015",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/market/accounts/{account.id}/refresh/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_apply_async.assert_not_called()

    @patch(
        "apps.market.tasks.accounts.refresh_oanda_account_snapshots.apply_async",
        side_effect=ConnectionError("broker down"),
    )
    def test_post_returns_unavailable_when_queueing_fails(
        self, mock_apply_async: Any, user: Any
    ) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-016",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f"/api/market/accounts/{account.id}/refresh/")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["error"] == "Failed to queue account snapshot refresh."
        mock_apply_async.assert_called_once()
        account.refresh_from_db()
        assert account.snapshot_refresh_status == OandaAccounts.SnapshotRefreshStatus.FAILED

    def test_get_refresh_status_for_owned_account_task(self, user: Any) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-017",
            api_type=ApiType.PRACTICE,
            is_active=True,
            snapshot_refresh_task_id="task-123",
            snapshot_refresh_status=OandaAccounts.SnapshotRefreshStatus.RUNNING,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/accounts/{account.id}/refresh/task-123/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == account.pk
        assert response.data["account_id"] == account.account_id
        assert response.data["task_id"] == "task-123"
        assert response.data["status"] == "running"

    def test_get_refresh_status_rejects_unknown_task(self, user: Any) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-018",
            api_type=ApiType.PRACTICE,
            is_active=True,
            snapshot_refresh_task_id="task-123",
            snapshot_refresh_status=OandaAccounts.SnapshotRefreshStatus.RUNNING,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/api/market/accounts/{account.id}/refresh/task-456/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
