"""
Integration tests for Athena import functionality.

Tests the complete flow from account creation to data import.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.utils import timezone

import pytest

from accounts.models import OandaAccount, SystemSettings, User
from trading.athena_import_task import (
    _get_instruments_to_import,
    _import_account_data,
    import_athena_data_daily,
    schedule_daily_athena_import,
)
from trading.historical_data_loader import TickDataPoint
from trading.tick_data_models import TickData


@pytest.mark.django_db
class TestAthenaImportSignal:
    """Test signal-triggered import on account creation."""

    def test_signal_triggers_import_on_account_creation(self, user):
        """Test that creating an account triggers Athena import."""
        with patch("trading.athena_import_task.import_athena_data_daily") as mock_task:
            mock_task.delay = Mock(return_value=Mock(id="test-task-id"))

            # Create account
            account = OandaAccount.objects.create(
                user=user,
                account_id="test-account-123",
                api_token="encrypted-token",
                api_type="practice",
                is_active=True,
            )

            # Verify task was triggered
            mock_task.delay.assert_called_once_with(account_id=account.id, days_back=7)

    def test_signal_not_triggered_for_inactive_account(self, user):
        """Test that inactive accounts don't trigger import."""
        with patch("trading.athena_import_task.import_athena_data_daily") as mock_task:
            mock_task.delay = Mock()

            # Create inactive account
            OandaAccount.objects.create(
                user=user,
                account_id="test-account-456",
                api_token="encrypted-token",
                api_type="practice",
                is_active=False,
            )

            # Verify task was NOT triggered
            mock_task.delay.assert_not_called()


@pytest.mark.django_db
class TestAthenaImportTask:
    """Test Athena import Celery tasks."""

    def test_get_instruments_to_import_from_settings(self):
        """Test getting instruments from SystemSettings."""
        # Create system settings with custom instruments
        SystemSettings.objects.create(
            pk=1,
            athena_instruments="EUR_USD,GBP_USD,USD_JPY",
        )

        instruments = _get_instruments_to_import()

        assert instruments == ["EUR_USD", "GBP_USD", "USD_JPY"]

    def test_get_instruments_to_import_defaults(self):
        """Test default instruments when settings not configured."""
        instruments = _get_instruments_to_import()

        # Should return default major pairs
        assert "EUR_USD" in instruments
        assert "GBP_USD" in instruments
        assert "USD_JPY" in instruments
        assert len(instruments) == 7

    @patch("trading.athena_import_task.HistoricalDataLoader")
    def test_import_account_data(self, mock_loader_class, user):
        """Test importing data for a specific account."""
        # Create account
        account = OandaAccount.objects.create(
            user=user,
            account_id="test-account",
            api_token="token",
            api_type="practice",
            is_active=True,
        )

        # Mock loader
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader

        # Mock tick data
        mock_tick = TickDataPoint(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )
        mock_loader.load_data.return_value = [mock_tick]

        # Import data
        start_date = timezone.now() - timedelta(days=1)
        end_date = timezone.now()
        instruments = ["EUR_USD"]

        ticks_imported = _import_account_data(
            account, mock_loader, instruments, start_date, end_date
        )

        # Verify
        assert ticks_imported == 1
        assert TickData.objects.filter(account=account).count() == 1

        tick = TickData.objects.first()
        assert tick is not None
        assert tick.instrument == "EUR_USD"
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1002")

    @patch("trading.athena_import_task.HistoricalDataLoader")
    def test_import_athena_data_daily_success(self, mock_loader_class, user):
        """Test successful daily import."""
        # Create account
        account = OandaAccount.objects.create(
            user=user,
            account_id="test-account",
            api_token="token",
            api_type="practice",
            is_active=True,
        )

        # Mock loader
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader

        # Mock tick data
        mock_tick = TickDataPoint(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )
        mock_loader.load_data.return_value = [mock_tick]

        # Run task
        result = import_athena_data_daily(account_id=account.id, days_back=1)

        # Verify
        assert result["success"] is True
        assert result["accounts_processed"] == 1
        assert result["total_ticks_imported"] > 0
        assert len(result["instruments"]) > 0

    @patch("trading.athena_import_task.HistoricalDataLoader")
    def test_import_athena_data_daily_no_accounts(self, mock_loader_class):
        """Test import with no active accounts."""
        result = import_athena_data_daily(days_back=1)

        # Verify
        assert result["accounts_processed"] == 0
        assert "No active OANDA accounts found" in result["errors"]

    @patch("trading.athena_import_task.import_athena_data_daily")
    def test_schedule_daily_athena_import(self, mock_import_task, user):
        """Test scheduled daily import."""
        # Create account
        OandaAccount.objects.create(
            user=user,
            account_id="test-account",
            api_token="token",
            api_type="practice",
            is_active=True,
        )

        # Mock task
        mock_import_task.delay = Mock(return_value=Mock(id="test-task-id"))

        # Run scheduler
        result = schedule_daily_athena_import()

        # Verify
        assert result["status"] == "scheduled"
        assert result["accounts_count"] == 1
        mock_import_task.delay.assert_called_once_with(days_back=1)


@pytest.mark.django_db
class TestDataDeduplication:
    """Test duplicate data handling."""

    def test_duplicate_ticks_not_imported(self, user):
        """Test that duplicate ticks are not imported."""
        account = OandaAccount.objects.create(
            user=user,
            account_id="test-account",
            api_token="token",
            api_type="practice",
            is_active=True,
        )

        timestamp = timezone.now()

        # Create first tick
        TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        # Try to create duplicate
        tick_point = TickDataPoint(
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        # Import should skip duplicate
        from trading.athena_import_task import _import_ticks_batch

        imported = _import_ticks_batch(account, [tick_point])

        # Verify only one tick exists
        assert imported == 0
        assert TickData.objects.filter(account=account).count() == 1

    def test_duplicate_ticks_with_different_timestamp(self, user):
        """Test that ticks with different timestamps are imported."""
        account = OandaAccount.objects.create(
            user=user,
            account_id="test-account",
            api_token="token",
            api_type="practice",
            is_active=True,
        )

        timestamp1 = timezone.now()
        timestamp2 = timestamp1 + timedelta(seconds=1)

        # Create first tick
        TickData.objects.create(
            account=account,
            instrument="EUR_USD",
            timestamp=timestamp1,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        # Create tick with different timestamp
        tick_point = TickDataPoint(
            instrument="EUR_USD",
            timestamp=timestamp2,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        # Import should succeed
        from trading.athena_import_task import _import_ticks_batch

        imported = _import_ticks_batch(account, [tick_point])

        # Verify both ticks exist
        assert imported == 1
        assert TickData.objects.filter(account=account).count() == 2


@pytest.mark.django_db
class TestCeleryBeatSchedule:
    """Test Celery Beat schedule configuration."""

    def test_daily_athena_import_scheduled(self):
        """Test that daily import is in Celery Beat schedule."""
        from django.conf import settings

        assert hasattr(settings, "CELERY_BEAT_SCHEDULE")
        beat_schedule = settings.CELERY_BEAT_SCHEDULE

        assert "daily-athena-import" in beat_schedule

        schedule_config = beat_schedule["daily-athena-import"]
        assert schedule_config["task"] == "trading.athena_import_task.schedule_daily_athena_import"
        assert "schedule" in schedule_config
        assert "options" in schedule_config


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
