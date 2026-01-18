"""
Unit tests for OandaAccounts model.

Tests model creation, validation, related_name access, and field constraints.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountsModel:
    """Test suite for OandaAccounts model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]
            email="test@example.com", password="testpass123", username="testuser"
        )

    @pytest.fixture
    def oanda_account(self, user):
        """Create a test OANDA account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-12345678-001",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
            balance=Decimal("10000.00"),
            margin_used=Decimal("0.00"),
            margin_available=Decimal("10000.00"),
            unrealized_pnl=Decimal("0.00"),
            is_active=True,
            is_default=False,
        )
        account.set_api_token("test-api-token-12345")
        account.save()
        return account

    def test_create_oanda_account(self, user):
        """Test creating an OandaAccounts instance with valid data."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-12345678-002",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
            balance=Decimal("5000.00"),
            margin_used=Decimal("100.00"),
            margin_available=Decimal("4900.00"),
            unrealized_pnl=Decimal("50.00"),
            is_active=True,
        )
        account.set_api_token("test-token")
        account.save()

        assert account.id is not None
        assert account.user == user
        assert account.account_id == "101-001-12345678-002"
        assert account.api_type == ApiType.PRACTICE
        assert account.jurisdiction == Jurisdiction.OTHER
        assert account.currency == "USD"
        assert account.balance == Decimal("5000.00")
        assert account.margin_used == Decimal("100.00")
        assert account.margin_available == Decimal("4900.00")
        assert account.unrealized_pnl == Decimal("50.00")
        assert account.is_active is True
        assert account.created_at is not None
        assert account.updated_at is not None

    def test_related_name_access(self, user, oanda_account):
        """Test accessing OandaAccounts through user's related_name."""
        accounts = user.oanda_accounts.all()
        assert accounts.count() == 1
        assert accounts.first() == oanda_account

    def test_unique_constraint(self, user, oanda_account):
        """Test unique constraint on (user, account_id, api_type)."""
        with pytest.raises(IntegrityError):
            OandaAccounts.objects.create(
                user=user,
                account_id=oanda_account.account_id,
                api_type=oanda_account.api_type,
                jurisdiction=Jurisdiction.OTHER,
                currency="USD",
            )

    def test_different_api_type_allowed(self, user, oanda_account):
        """Test that same account_id with different api_type is allowed."""
        live_account = OandaAccounts.objects.create(
            user=user,
            account_id=oanda_account.account_id,
            api_type=ApiType.LIVE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
        )
        assert live_account.id is not None
        assert live_account.account_id == oanda_account.account_id
        assert live_account.api_type != oanda_account.api_type

    def test_api_token_encryption(self, oanda_account):
        """Test that API token is encrypted and can be decrypted."""
        original_token = "my-secret-api-token-12345"
        oanda_account.set_api_token(original_token)
        oanda_account.save()

        # Token should be encrypted in database
        assert oanda_account.api_token != original_token

        # Should be able to decrypt
        decrypted_token = oanda_account.get_api_token()
        assert decrypted_token == original_token

    def test_update_balance(self, oanda_account):
        """Test updating account balance and margin fields."""
        oanda_account.update_balance(
            balance=15000.00, margin_used=500.00, margin_available=14500.00, unrealized_pnl=100.00
        )

        oanda_account.refresh_from_db()
        assert oanda_account.balance == Decimal("15000.00")
        assert oanda_account.margin_used == Decimal("500.00")
        assert oanda_account.margin_available == Decimal("14500.00")
        assert oanda_account.unrealized_pnl == Decimal("100.00")

    def test_activate_deactivate(self, oanda_account):
        """Test activating and deactivating an account."""
        oanda_account.deactivate()
        oanda_account.refresh_from_db()
        assert oanda_account.is_active is False

        oanda_account.activate()
        oanda_account.refresh_from_db()
        assert oanda_account.is_active is True

    def test_set_as_default(self, user, oanda_account):
        """Test setting an account as default."""
        # Create another account
        account2 = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-12345678-003",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
        )

        # Set first account as default
        oanda_account.set_as_default()
        oanda_account.refresh_from_db()
        assert oanda_account.is_default is True

        # Set second account as default
        account2.set_as_default()
        account2.refresh_from_db()
        oanda_account.refresh_from_db()

        # Only second account should be default
        assert account2.is_default is True
        assert oanda_account.is_default is False

    def test_api_hostname_practice(self, oanda_account):
        """Test api_hostname property for practice account."""
        oanda_account.account_id = "101-001-12345678-001"
        oanda_account.api_type = ApiType.PRACTICE
        hostname = oanda_account.api_hostname
        assert "practice" in hostname.lower() or "fxpractice" in hostname.lower()

    def test_api_hostname_live(self, user):
        """Test api_hostname property for live account."""
        live_account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-12345678-001",
            api_type=ApiType.LIVE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
        )
        hostname = live_account.api_hostname
        assert "practice" not in hostname.lower()

    def test_str_representation(self, oanda_account):
        """Test string representation of OandaAccounts."""
        str_repr = str(oanda_account)
        assert oanda_account.user.email in str_repr
        assert oanda_account.account_id in str_repr
        assert oanda_account.api_type in str_repr

    def test_ordering(self, user):
        """Test that accounts are ordered by created_at descending."""
        account1 = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-12345678-001",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
        )
        account2 = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-12345678-002",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            currency="USD",
        )

        accounts = OandaAccounts.objects.filter(user=user)
        assert accounts[0] == account2  # Most recent first
        assert accounts[1] == account1

    def test_decimal_precision(self, oanda_account):
        """Test decimal field precision for balance and margin fields."""
        oanda_account.balance = Decimal("12345.67")
        oanda_account.margin_used = Decimal("123.45")
        oanda_account.margin_available = Decimal("12222.22")
        oanda_account.unrealized_pnl = Decimal("-50.50")
        oanda_account.save()

        oanda_account.refresh_from_db()
        assert oanda_account.balance == Decimal("12345.67")
        assert oanda_account.margin_used == Decimal("123.45")
        assert oanda_account.margin_available == Decimal("12222.22")
        assert oanda_account.unrealized_pnl == Decimal("-50.50")
