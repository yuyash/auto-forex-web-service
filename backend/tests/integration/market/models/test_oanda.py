"""Unit tests for OandaAccounts model."""
from typing import Any


import pytest
from django.contrib.auth import get_user_model

from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountsModel:
    """Test OandaAccounts model."""

    def test_create_oanda_account(self, user: Any) -> None:
        """Test creating an OANDA account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_token="test_token",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
        )

        assert account.user == user
        assert account.account_id == "101-001-1234567-001"
        assert account.api_type == ApiType.PRACTICE
        assert account.jurisdiction == Jurisdiction.OTHER
        assert account.is_active is True
        assert account.is_default is False

    def test_set_and_get_api_token(self, user: Any) -> None:
        """Test encrypting and decrypting API token."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        test_token = "test_api_token_12345"
        account.set_api_token(test_token)
        account.save()

        # Token should be encrypted in database
        assert account.api_token != test_token

        # Should decrypt correctly
        decrypted = account.get_api_token()
        assert decrypted == test_token

    def test_api_hostname_practice(self, user: Any) -> None:
        """Test API hostname for practice account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        hostname = account.api_hostname
        assert "practice" in hostname.lower() or "fxpractice" in hostname.lower()

    def test_api_hostname_live(self, user: Any) -> None:
        """Test API hostname for live account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
        )

        hostname = account.api_hostname
        assert "practice" not in hostname.lower()

    def test_update_balance(self, user: Any) -> None:
        """Test updating account balance."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        account.update_balance(
            balance=10000.0,
            margin_used=1000.0,
            margin_available=9000.0,
            unrealized_pnl=100.0,
        )

        account.refresh_from_db()
        assert float(account.balance) == 10000.0
        assert float(account.margin_used) == 1000.0
        assert float(account.margin_available) == 9000.0
        assert float(account.unrealized_pnl) == 100.0

    def test_activate_deactivate(self, user: Any) -> None:
        """Test activating and deactivating account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=False,
        )

        account.activate()
        account.refresh_from_db()
        assert account.is_active is True

        account.deactivate()
        account.refresh_from_db()
        assert account.is_active is False

    def test_set_as_default(self, user: Any) -> None:
        """Test setting account as default."""
        account1 = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_default=True,
        )

        account2 = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        account2.set_as_default()

        account1.refresh_from_db()
        account2.refresh_from_db()

        assert account1.is_default is False
        assert account2.is_default is True

    def test_str_representation(self, user: Any) -> None:
        """Test string representation."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        str_repr = str(account)
        assert user.email in str_repr
        assert "101-001-1234567-001" in str_repr
        assert ApiType.PRACTICE in str_repr
