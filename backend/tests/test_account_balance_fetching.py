"""
Unit tests for account balance fetching Celery tasks.

This module tests:
- Celery task execution with mocked OANDA API
- Balance and margin field updates
- Periodic scheduling
- Error handling for API failures

Requirements: 4.1, 4.5
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from celery.exceptions import Retry

from accounts.models import OandaAccount, User
from accounts.tasks import fetch_account_balance, fetch_all_active_account_balances


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def oanda_account(db, user):
    """Create a test OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        currency="USD",
        balance=Decimal("10000.00"),
        margin_used=Decimal("500.00"),
        margin_available=Decimal("9500.00"),
        unrealized_pnl=Decimal("0.00"),
        is_active=True,
    )
    # Set encrypted API token
    account.set_api_token("test_api_token_12345")
    account.save()
    return account


@pytest.fixture
def inactive_oanda_account(db, user):
    """Create an inactive test OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-7654321-001",
        api_type="practice",
        currency="USD",
        balance=Decimal("5000.00"),
        is_active=False,
    )
    account.set_api_token("test_api_token_inactive")
    account.save()
    return account


@pytest.mark.django_db
class TestFetchAccountBalance:
    """Test suite for fetch_account_balance Celery task."""

    def test_successful_balance_fetch(self, oanda_account):
        """Test successful balance and margin fetch from OANDA API."""
        # Mock the v20 API response
        mock_account_data = Mock()
        mock_account_data.balance = "12500.50"
        mock_account_data.marginUsed = "750.25"
        mock_account_data.marginAvailable = "11750.25"
        mock_account_data.unrealizedPL = "250.50"

        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = {"account": mock_account_data}

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            mock_api.account.get.return_value = mock_response
            mock_context.return_value = mock_api

            # Execute the task
            result = fetch_account_balance(oanda_account.id)

            # Verify the result
            assert result["success"] is True
            assert result["error"] is None
            assert result["balance"] == 12500.50
            assert result["margin_used"] == 750.25
            assert result["margin_available"] == 11750.25
            assert result["unrealized_pnl"] == 250.50

            # Verify the database was updated
            oanda_account.refresh_from_db()
            assert oanda_account.balance == Decimal("12500.50")
            assert oanda_account.margin_used == Decimal("750.25")
            assert oanda_account.margin_available == Decimal("11750.25")
            assert oanda_account.unrealized_pnl == Decimal("250.50")

            # Verify API was called correctly
            mock_context.assert_called_once()
            mock_api.account.get.assert_called_once_with(oanda_account.account_id)

    def test_balance_fetch_with_zero_margin(self, oanda_account):
        """Test balance fetch when margin values are None (no open positions)."""
        # Mock the v20 API response with None margin values
        mock_account_data = Mock()
        mock_account_data.balance = "10000.00"
        mock_account_data.marginUsed = None
        mock_account_data.marginAvailable = None
        mock_account_data.unrealizedPL = None

        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = {"account": mock_account_data}

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            mock_api.account.get.return_value = mock_response
            mock_context.return_value = mock_api

            # Execute the task
            result = fetch_account_balance(oanda_account.id)

            # Verify the result
            assert result["success"] is True
            assert result["balance"] == 10000.00
            assert result["margin_used"] == 0.0
            assert result["margin_available"] == 0.0
            assert result["unrealized_pnl"] == 0.0

            # Verify the database was updated
            oanda_account.refresh_from_db()
            assert oanda_account.balance == Decimal("10000.00")
            assert oanda_account.margin_used == Decimal("0.00")
            assert oanda_account.margin_available == Decimal("0.00")
            assert oanda_account.unrealized_pnl == Decimal("0.00")

    def test_balance_fetch_nonexistent_account(self):
        """Test balance fetch for non-existent account."""
        # Execute the task with non-existent account ID
        result = fetch_account_balance(99999)

        # Verify the result
        assert result["success"] is False
        assert "does not exist" in result["error"]
        assert result["balance"] is None
        assert result["margin_used"] is None
        assert result["margin_available"] is None
        assert result["unrealized_pnl"] is None

    def test_balance_fetch_inactive_account(self, inactive_oanda_account):
        """Test balance fetch skips inactive accounts."""
        # Execute the task
        result = fetch_account_balance(inactive_oanda_account.id)

        # Verify the result
        assert result["success"] is False
        assert result["error"] == "Account is not active"
        assert result["balance"] is None

        # Verify the database was not updated
        inactive_oanda_account.refresh_from_db()
        assert inactive_oanda_account.balance == Decimal("5000.00")

    def test_balance_fetch_api_error_status(self, oanda_account):
        """Test balance fetch handles API error status codes."""
        # Mock the v20 API response with error status
        mock_response = Mock()
        mock_response.status = 401
        mock_response.body = {"errorMessage": "Unauthorized"}

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            mock_api.account.get.return_value = mock_response
            mock_context.return_value = mock_api

            # Execute the task
            result = fetch_account_balance(oanda_account.id)

            # Verify the result
            assert result["success"] is False
            assert "status 401" in result["error"]
            assert result["balance"] is None

            # Verify the database was not updated
            oanda_account.refresh_from_db()
            assert oanda_account.balance == Decimal("10000.00")

    def test_balance_fetch_no_account_data(self, oanda_account):
        """Test balance fetch handles missing account data in response."""
        # Mock the v20 API response without account data
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = {}

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            mock_api.account.get.return_value = mock_response
            mock_context.return_value = mock_api

            # Execute the task
            result = fetch_account_balance(oanda_account.id)

            # Verify the result
            assert result["success"] is False
            assert "No account data" in result["error"]
            assert result["balance"] is None

    def test_balance_fetch_connection_error_retry(self, oanda_account):
        """Test balance fetch retries on connection errors."""
        from v20.errors import V20ConnectionError

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            mock_api.account.get.side_effect = V20ConnectionError("Connection failed")
            mock_context.return_value = mock_api

            # Mock the task's retry method
            with patch.object(fetch_account_balance, "retry", side_effect=Retry()) as mock_retry:
                # Execute the task and expect Retry exception
                with pytest.raises(Retry):
                    fetch_account_balance(oanda_account.id)

                # Verify retry was called
                mock_retry.assert_called_once()

    def test_balance_fetch_timeout_error_retry(self, oanda_account):
        """Test balance fetch retries on timeout errors."""
        from v20.errors import V20Timeout

        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_api = MagicMock()
            # V20Timeout requires a 'type' argument
            mock_api.account.get.side_effect = V20Timeout("Request timeout", "TIMEOUT")
            mock_context.return_value = mock_api

            # Mock the task's retry method
            with patch.object(fetch_account_balance, "retry", side_effect=Retry()) as mock_retry:
                # Execute the task and expect Retry exception
                with pytest.raises(Retry):
                    fetch_account_balance(oanda_account.id)

                # Verify retry was called
                mock_retry.assert_called_once()

    def test_balance_fetch_unexpected_error(self, oanda_account):
        """Test balance fetch handles unexpected errors gracefully."""
        with patch("accounts.tasks.v20.Context") as mock_context:
            mock_context.side_effect = Exception("Unexpected error")

            # Execute the task
            result = fetch_account_balance(oanda_account.id)

            # Verify the result
            assert result["success"] is False
            assert "Unexpected error" in result["error"]
            assert result["balance"] is None

            # Verify the database was not updated
            oanda_account.refresh_from_db()
            assert oanda_account.balance == Decimal("10000.00")


@pytest.mark.django_db
class TestFetchAllActiveAccountBalances:
    """Test suite for fetch_all_active_account_balances Celery task."""

    def test_fetch_all_active_accounts(self, user):
        """Test fetching balances for all active accounts."""
        # Create multiple active accounts
        account1 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1111111-001",
            api_type="practice",
            is_active=True,
        )
        account1.set_api_token("token1")
        account1.save()

        account2 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-2222222-001",
            api_type="practice",
            is_active=True,
        )
        account2.set_api_token("token2")
        account2.save()

        # Create an inactive account (should be skipped)
        account3 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-3333333-001",
            api_type="practice",
            is_active=False,
        )
        account3.set_api_token("token3")
        account3.save()

        # Mock the fetch_account_balance task
        with patch("accounts.tasks.fetch_account_balance.delay") as mock_delay:
            # Execute the task
            result = fetch_all_active_account_balances()

            # Verify the result
            assert result["total_accounts"] == 2
            assert result["tasks_scheduled"] == 2

            # Verify fetch_account_balance was called for each active account
            assert mock_delay.call_count == 2
            called_account_ids = [call[0][0] for call in mock_delay.call_args_list]
            assert account1.id in called_account_ids
            assert account2.id in called_account_ids
            assert account3.id not in called_account_ids

    def test_fetch_all_no_active_accounts(self, user):
        """Test fetching balances when no active accounts exist."""
        # Create only inactive accounts
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1111111-001",
            api_type="practice",
            is_active=False,
        )
        account.set_api_token("token")
        account.save()

        # Mock the fetch_account_balance task
        with patch("accounts.tasks.fetch_account_balance.delay") as mock_delay:
            # Execute the task
            result = fetch_all_active_account_balances()

            # Verify the result
            assert result["total_accounts"] == 0
            assert result["tasks_scheduled"] == 0

            # Verify fetch_account_balance was not called
            mock_delay.assert_not_called()


@pytest.mark.django_db
class TestPeriodicScheduling:
    """Test suite for periodic scheduling configuration."""

    def test_celery_beat_schedule_configured(self):
        """Test that Celery Beat schedule is properly configured."""
        from django.conf import settings

        # Verify CELERY_BEAT_SCHEDULE exists
        assert hasattr(settings, "CELERY_BEAT_SCHEDULE")
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        assert "fetch-all-account-balances" in beat_schedule

        # Verify schedule configuration
        schedule_config = beat_schedule["fetch-all-account-balances"]
        assert schedule_config["task"] == "accounts.tasks.fetch_all_active_account_balances"
        assert schedule_config["schedule"] == 120.0  # 2 minutes

    def test_task_schedule_interval(self):
        """Test that the task is scheduled to run every 2 minutes."""
        from typing import Any, Dict

        from django.conf import settings

        beat_schedule: Dict[str, Any] = settings.CELERY_BEAT_SCHEDULE
        schedule_config: Dict[str, Any] = beat_schedule["fetch-all-account-balances"]

        # Verify the schedule is 120 seconds (2 minutes)
        assert schedule_config["schedule"] == 120.0

        # Verify task expiration is set
        assert "options" in schedule_config
        options: Dict[str, Any] = schedule_config["options"]
        assert "expires" in options
        assert options["expires"] == 60.0
