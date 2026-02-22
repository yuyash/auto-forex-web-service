"""Unit tests for OandaAccountsSerializer."""

from typing import Any


import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountsSerializer:
    """Test OandaAccountsSerializer."""

    def test_serialize_account(self, user: Any) -> None:
        """Test serializing an OANDA account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            balance=10000.00,
        )

        serializer = OandaAccountsSerializer(account)
        data = serializer.data

        assert data["account_id"] == "101-001-1234567-001"
        assert data["api_type"] == ApiType.PRACTICE
        assert data["jurisdiction"] == Jurisdiction.OTHER
        assert float(data["balance"]) == 10000.00
        assert "api_token" not in data  # Should not be in output

    def test_create_account(self, user: Any) -> None:
        """Test creating an account via serializer."""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {
            "account_id": "101-001-1234567-002",
            "api_token": "test_token_12345",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": Jurisdiction.OTHER,
        }

        serializer = OandaAccountsSerializer(data=data, context={"request": request})
        assert serializer.is_valid(), serializer.errors

        account = serializer.save()
        assert account.account_id == "101-001-1234567-002"
        assert account.user == user
        assert account.get_api_token() == "test_token_12345"

    def test_validate_api_type(self, user: Any) -> None:
        """Test API type validation."""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {
            "account_id": "101-001-1234567-003",
            "api_token": "test_token",
            "api_type": "invalid_type",
            "jurisdiction": Jurisdiction.OTHER,
        }

        serializer = OandaAccountsSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "api_type" in serializer.errors

    def test_validate_jurisdiction(self, user: Any) -> None:
        """Test jurisdiction validation."""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {
            "account_id": "101-001-1234567-004",
            "api_token": "test_token",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": "invalid_jurisdiction",
        }

        serializer = OandaAccountsSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "jurisdiction" in serializer.errors

    def test_unique_account_validation(self, user: Any) -> None:
        """Test that duplicate accounts are rejected."""
        # Create first account
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-005",
            api_type=ApiType.PRACTICE,
        )

        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        # Try to create duplicate
        data = {
            "account_id": "101-001-1234567-005",
            "api_token": "test_token",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": Jurisdiction.OTHER,
        }

        serializer = OandaAccountsSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "account_id" in serializer.errors

    def test_update_account(self, user: Any) -> None:
        """Test updating an account via serializer."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-006",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        factory = APIRequestFactory()
        request = factory.put("/")
        request.user = user

        data = {"is_active": False}

        serializer = OandaAccountsSerializer(
            account, data=data, partial=True, context={"request": request}
        )
        assert serializer.is_valid(), serializer.errors

        updated_account = serializer.save()
        assert updated_account.is_active is False

    def test_first_account_is_default(self, user: Any) -> None:
        """Test that first account is automatically set as default."""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {
            "account_id": "101-001-1234567-007",
            "api_token": "test_token",
            "api_type": ApiType.PRACTICE,
            "jurisdiction": Jurisdiction.OTHER,
        }

        serializer = OandaAccountsSerializer(data=data, context={"request": request})
        assert serializer.is_valid()

        account = serializer.save()
        assert account.is_default is True
