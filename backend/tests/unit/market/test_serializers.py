"""Unit tests for market serializers."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.serializers import (
    OandaAccountsSerializer,
    OandaApiHealthStatusSerializer,
)

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountsSerializer:
    """Test OandaAccountsSerializer."""

    def test_serialize_oanda_account(self):
        """Test serializing OANDA account."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
            balance=Decimal("10000.00"),
        )

        serializer = OandaAccountsSerializer(account)
        data = serializer.data

        assert data["account_id"] == "001-001-1234567-001"
        assert data["api_type"] == ApiType.PRACTICE
        # api_token should not be exposed in serialization


@pytest.mark.django_db
class TestOandaApiHealthStatusSerializer:
    """Test OandaApiHealthStatusSerializer."""

    def test_serialize_health_status(self):
        """Test serializing API health status."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
        )

        from apps.market.models import OandaApiHealthStatus

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
            latency_ms=150,
            http_status=200,
        )

        serializer = OandaApiHealthStatusSerializer(health)
        data = serializer.data

        assert data["is_available"] is True
        assert data["latency_ms"] == 150
        assert data["http_status"] == 200
