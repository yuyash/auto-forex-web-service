"""
Unit tests for TickData model.

Tests cover:
- TickData model field validation
- Timestamp indexing
- Composite index on (instrument, timestamp)
- Data retention policy
- Mid price and spread calculations

Requirements: 7.1, 7.2, 12.1
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import override_settings
from django.utils import timezone

import pytest

from accounts.models import OandaAccount, User
from trading.tick_data_models import TickData


@pytest.mark.django_db
class TestTickDataModel:
    """Test cases for TickData model."""

    def test_tick_data_creation(self) -> None:
        """Test creating a tick data record."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        tick = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        assert tick.account == account
        assert tick.instrument == "EUR_USD"
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1005")
        assert tick.mid == Decimal("1.10025")
        assert tick.spread == Decimal("0.00050")
        assert tick.created_at is not None

    def test_tick_data_field_validation(self) -> None:
        """Test TickData model field validation."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        tick = TickData.objects.create(
            account=account,
            instrument="GBP_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.2500"),
            ask=Decimal("1.2504"),
        )

        # Verify field types and constraints
        assert isinstance(tick.instrument, str)
        assert len(tick.instrument) <= 10
        assert isinstance(tick.bid, Decimal)
        assert isinstance(tick.ask, Decimal)
        assert isinstance(tick.mid, Decimal)
        assert isinstance(tick.spread, Decimal)

    def test_tick_data_mid_calculation(self) -> None:
        """Test mid price calculation."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Test automatic mid calculation
        tick = TickData.objects.create(
            account=account,
            instrument="USD_JPY",
            timestamp=timezone.now(),
            bid=Decimal("150.00"),
            ask=Decimal("150.10"),
        )

        expected_mid = (Decimal("150.00") + Decimal("150.10")) / Decimal("2")
        assert tick.mid == expected_mid
        assert tick.mid == Decimal("150.05")

    def test_tick_data_spread_calculation(self) -> None:
        """Test spread calculation."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Test automatic spread calculation
        tick = TickData.objects.create(
            account=account,
            instrument="AUD_USD",
            timestamp=timezone.now(),
            bid=Decimal("0.6500"),
            ask=Decimal("0.6505"),
        )

        expected_spread = Decimal("0.6505") - Decimal("0.6500")
        assert tick.spread == expected_spread
        assert tick.spread == Decimal("0.0005")

    def test_tick_data_manual_mid_and_spread(self) -> None:
        """Test that manually provided mid and spread are preserved."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Provide manual mid and spread
        tick = TickData.objects.create(
            account=account,
            instrument="EUR_GBP",
            timestamp=timezone.now(),
            bid=Decimal("0.8500"),
            ask=Decimal("0.8505"),
            mid=Decimal("0.8502"),  # Manual value
            spread=Decimal("0.0005"),  # Manual value
        )

        # Manual values should be preserved
        assert tick.mid == Decimal("0.8502")
        assert tick.spread == Decimal("0.0005")

    def test_tick_data_calculate_mid_static_method(self) -> None:
        """Test static method for mid price calculation."""
        bid = Decimal("1.1000")
        ask = Decimal("1.1005")

        mid = TickData.calculate_mid(bid, ask)

        assert mid == Decimal("1.10025")
        assert mid == (bid + ask) / Decimal("2")

    def test_tick_data_calculate_spread_static_method(self) -> None:
        """Test static method for spread calculation."""
        bid = Decimal("1.1000")
        ask = Decimal("1.1005")

        spread = TickData.calculate_spread(bid, ask)

        assert spread == Decimal("0.00050")
        assert spread == ask - bid

    def test_tick_data_timestamp_indexing(self) -> None:
        """Test timestamp indexing for efficient queries."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Create multiple ticks with different timestamps
        now = timezone.now()
        for i in range(5):
            TickData.objects.create(
                account=account,
                instrument="EUR_USD",
                timestamp=now - timedelta(minutes=i),
                bid=Decimal("1.1000"),
                ask=Decimal("1.1005"),
            )

        # Query by timestamp range
        start_time = now - timedelta(minutes=3)
        end_time = now
        ticks = TickData.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time,
        )

        assert ticks.count() == 4  # 0, 1, 2, 3 minutes ago

        # Verify index exists on timestamp field
        indexes = connection.introspection.get_constraints(
            connection.cursor(), TickData._meta.db_table
        )
        timestamp_indexed = any("timestamp" in idx["columns"] for idx in indexes.values())
        assert timestamp_indexed is True

    def test_tick_data_composite_index(self) -> None:
        """Test composite index on (instrument, timestamp)."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Create ticks for different instrument
        now = timezone.now()
        for instrument in ["EUR_USD", "GBP_USD", "USD_JPY"]:
            for i in range(3):
                TickData.objects.create(
                    account=account,
                    instrument=instrument,
                    timestamp=now - timedelta(minutes=i),
                    bid=Decimal("1.1000"),
                    ask=Decimal("1.1005"),
                )

        # Query by instrument and timestamp (should use composite index)
        start_time = now - timedelta(minutes=2)
        ticks = TickData.objects.filter(
            instrument="EUR_USD",
            timestamp__gte=start_time,
        )

        assert ticks.count() == 3

        # Verify composite index exists
        indexes = connection.introspection.get_constraints(
            connection.cursor(), TickData._meta.db_table
        )
        composite_index_exists = any(
            "instrument" in idx["columns"] and "timestamp" in idx["columns"]
            for idx in indexes.values()
        )
        assert composite_index_exists is True

    def test_tick_data_get_retention_days_default(self) -> None:
        """Test default retention days."""
        retention_days = TickData.get_retention_days()
        assert retention_days == 90  # Default value

    @override_settings(TICK_DATA_RETENTION_DAYS=30)
    def test_tick_data_get_retention_days_custom(self) -> None:
        """Test custom retention days from settings."""
        retention_days = TickData.get_retention_days()
        assert retention_days == 30

    def test_tick_data_cleanup_old_data(self) -> None:
        """Test data retention policy cleanup."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        now = timezone.now()

        # Create old tick data (100 days old)
        old_tick = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=now - timedelta(days=100),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )
        old_tick.created_at = now - timedelta(days=100)
        old_tick.save()

        # Create recent tick data (10 days old)
        recent_tick = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=now - timedelta(days=10),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )
        recent_tick.created_at = now - timedelta(days=10)
        recent_tick.save()

        # Verify both exist
        assert TickData.objects.count() == 2

        # Cleanup with 90-day retention
        deleted_count = TickData.cleanup_old_data(retention_days=90)

        # Old tick should be deleted, recent tick should remain
        assert deleted_count == 1
        assert TickData.objects.count() == 1
        assert TickData.objects.filter(id=recent_tick.id).exists()
        assert not TickData.objects.filter(id=old_tick.id).exists()

    def test_tick_data_cleanup_with_custom_retention(self) -> None:
        """Test cleanup with custom retention period."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        now = timezone.now()

        # Create tick data at different ages
        for days_ago in [5, 15, 35, 65]:
            tick = TickData.objects.create(
                account=account,
                instrument="EUR_USD",
                timestamp=now - timedelta(days=days_ago),
                bid=Decimal("1.1000"),
                ask=Decimal("1.1005"),
            )
            tick.created_at = now - timedelta(days=days_ago)
            tick.save()

        assert TickData.objects.count() == 4

        # Cleanup with 30-day retention
        deleted_count = TickData.cleanup_old_data(retention_days=30)

        # Should delete 2 ticks (35 and 65 days old)
        assert deleted_count == 2
        assert TickData.objects.count() == 2

    def test_tick_data_cleanup_no_old_data(self) -> None:
        """Test cleanup when no old data exists."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Create only recent data
        TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        # Cleanup should delete nothing
        deleted_count = TickData.cleanup_old_data(retention_days=90)

        assert deleted_count == 0
        assert TickData.objects.count() == 1

    def test_tick_data_ordering(self) -> None:
        """Test default ordering by timestamp descending."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        now = timezone.now()

        # Create ticks in random order
        tick1 = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=now - timedelta(minutes=2),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )
        tick2 = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )
        tick3 = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=now - timedelta(minutes=1),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        # Query all ticks
        ticks = list(TickData.objects.all())

        # Should be ordered by timestamp descending (newest first)
        assert ticks[0].id == tick2.id  # Most recent
        assert ticks[1].id == tick3.id  # Middle
        assert ticks[2].id == tick1.id  # Oldest

    def test_tick_data_str_representation(self) -> None:
        """Test string representation of TickData."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        tick = TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        str_repr = str(tick)
        assert "EUR_USD" in str_repr
        assert "1.1000" in str_repr
        assert "1.1005" in str_repr

    def test_tick_data_multiple_accounts(self) -> None:
        """Test tick data for multiple accounts."""
        user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass123",
        )
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="pass123",
        )

        account1 = OandaAccount.objects.create(
            user=user1,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        account2 = OandaAccount.objects.create(
            user=user2,
            account_id="001-001-1234567-002",
            api_type="practice",
        )
        account2.set_api_token("token2")
        account2.save()

        # Create ticks for both accounts
        tick1 = TickData.objects.create(
            account=account1,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )
        tick2 = TickData.objects.create(
            account=account2,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        # Verify account-specific queries
        assert account1.tick_data.count() == 1
        assert account2.tick_data.count() == 1
        assert tick1 in account1.tick_data.all()
        assert tick2 in account2.tick_data.all()

    def test_tick_data_account_cascade_delete(self) -> None:
        """Test that tick data is deleted when account is deleted."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token")
        account.save()

        # Create tick data
        TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1005"),
        )

        assert TickData.objects.count() == 1

        # Delete account
        account.delete()

        # Tick data should be deleted (cascade)
        assert TickData.objects.count() == 0
