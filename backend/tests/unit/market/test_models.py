"""Unit tests for market models."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.market.enums import ApiType
from apps.market.models import (
    CeleryTaskStatus,
    MarketEvent,
    OandaAccounts,
    OandaApiHealthStatus,
    TickData,
)

User = get_user_model()


@pytest.mark.django_db
class TestOandaAccountsModel:
    """Test OandaAccounts model - extended tests."""

    def test_set_api_token_encrypts_token(self):
        """Test that set_api_token encrypts the token."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="",
            api_type=ApiType.PRACTICE,
        )

        plain_token = "test_api_token_12345"
        account.set_api_token(plain_token)

        # Token should be encrypted (not equal to plain text)
        assert account.api_token != plain_token
        # Should be able to decrypt it
        assert account.get_api_token()  # type: ignore[attr-defined] == plain_token

    def test_multiple_accounts_same_user(self):
        """Test user can have multiple OANDA accounts."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        account1 = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token_1",
            api_type=ApiType.PRACTICE,
        )

        account2 = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_token="encrypted_token_2",
            api_type=ApiType.LIVE,
        )

        assert user.oanda_accounts.count() == 2
        assert account1.user == account2.user


@pytest.mark.django_db
class TestTickDataModel:
    """Test TickData model."""

    def test_create_tick_data(self):
        """Test creating tick data."""
        tick = TickData.objects.create(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
        )

        assert tick.instrument == "EUR_USD"
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1002")

    def test_tick_data_composite_primary_key(self):
        """Test tick data has composite primary key."""
        timestamp = timezone.now()

        TickData.objects.create(
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
        )

        # Same instrument and timestamp should fail
        with pytest.raises(IntegrityError):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=timestamp,
                bid=Decimal("1.1001"),
                ask=Decimal("1.1003"),
            )


@pytest.mark.django_db
class TestMarketEventModel:
    """Test MarketEvent model."""

    def test_create_market_event(self):
        """Test creating a market event."""
        event = MarketEvent.objects.create(
            event_type="price_update",
            severity="info",
            description="Price updated for EUR_USD",
        )

        assert event.event_type == "price_update"
        assert event.severity == "info"
        assert event.description == "Price updated for EUR_USD"

    def test_market_event_with_details(self):
        """Test market event with JSON details."""
        details = {
            "instrument": "EUR_USD",
            "bid": "1.1000",
            "ask": "1.1002",
        }

        event = MarketEvent.objects.create(
            event_type="price_update",
            severity="info",
            description="Price updated",
            details=details,
        )

        assert event.details == details
        assert event.details["instrument"] == "EUR_USD"


@pytest.mark.django_db
class TestCeleryTaskStatusModel:
    """Test CeleryTaskStatus model."""

    def test_create_celery_task_status(self):
        """Test creating celery task status."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.collect_tick_data",
            instance_key="test-instance",
            celery_task_id="test-task-123",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task.task_name == "market.tasks.collect_tick_data"
        assert task.instance_key == "test-instance"
        assert task.celery_task_id == "test-task-123"
        assert task.status == CeleryTaskStatus.Status.RUNNING

    def test_update_task_status(self):
        """Test updating task status."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.collect_tick_data",
            instance_key="test-instance",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        task.status = CeleryTaskStatus.Status.COMPLETED
        task.save()

        updated_task = CeleryTaskStatus.objects.get(id=task.id)
        assert updated_task.status == CeleryTaskStatus.Status.COMPLETED


@pytest.mark.django_db
class TestOandaApiHealthStatusModel:
    """Test OandaApiHealthStatus model."""

    def test_create_health_status(self):
        """Test creating API health status."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
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

    def test_health_status_with_error(self):
        """Test health status with error message."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
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

        health = OandaApiHealthStatus.objects.create(
            account=account,
            is_available=False,
            latency_ms=0,
            http_status=500,
            error_message="Connection timeout",
        )

        assert health.is_available is False
        assert health.error_message == "Connection timeout"
        assert health.http_status == 500
