"""Unit tests for OandaApiHealthStatus model."""

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts, OandaApiHealthStatus

User = get_user_model()


@pytest.mark.django_db
class TestOandaApiHealthStatusModel:
    """Test OandaApiHealthStatus model."""

    def test_create_health_status(self, user: Any) -> None:
        """Test creating health status."""
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

        assert health.account == account
        assert health.is_available is True
        assert health.latency_ms == 150
        assert health.http_status == 200

    def test_health_status_with_error(self, user: Any) -> None:
        """Test health status with error."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
        )

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=False,
            http_status=500,
            error_message="Connection timeout",
        )

        assert health.is_available is False
        assert health.http_status == 500
        assert health.error_message == "Connection timeout"

    def test_str_representation(self, user: Any) -> None:
        """Test string representation."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
            http_status=200,
        )

        str_repr = str(health)
        assert "101-001-1234567-003" in str_repr
        assert "200" in str_repr
        assert "available=True" in str_repr

    def test_ordering(self, user: Any) -> None:
        """Test that health statuses are ordered by checked_at descending."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-004",
            api_type=ApiType.PRACTICE,
        )

        # Create multiple health checks
        health1 = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
            checked_at=timezone.now() - timedelta(hours=2),
        )

        health2 = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=True,
            checked_at=timezone.now(),
        )

        # Query should return newest first
        statuses = list(OandaApiHealthStatus.objects.filter(account=account))
        assert statuses[0].id == health2.id
        assert statuses[1].id == health1.id
