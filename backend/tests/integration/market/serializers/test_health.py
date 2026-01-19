"""Unit tests for OandaApiHealthStatusSerializer."""
from typing import Any


import pytest
from django.contrib.auth import get_user_model

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts, OandaApiHealthStatus
from apps.market.serializers import OandaApiHealthStatusSerializer

User = get_user_model()


@pytest.mark.django_db
class TestOandaApiHealthStatusSerializer:
    """Test OandaApiHealthStatusSerializer."""

    def test_serialize_health_status(self, user: Any) -> None:
        """Test serializing health status."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
            latency_ms=150,
            http_status=200,
        )

        serializer = OandaApiHealthStatusSerializer(health)
        data = serializer.data

        assert data["oanda_account_id"] == "101-001-1234567-001"
        assert data["api_type"] == ApiType.PRACTICE
        assert data["is_available"] is True
        assert data["latency_ms"] == 150
        assert data["http_status"] == 200

    def test_all_fields_read_only(self, user: Any) -> None:
        """Test that all fields are read-only."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
        )

        serializer = OandaApiHealthStatusSerializer(health)

        # All fields should be in read_only_fields
        assert len(serializer.Meta.read_only_fields) == len(serializer.Meta.fields)
