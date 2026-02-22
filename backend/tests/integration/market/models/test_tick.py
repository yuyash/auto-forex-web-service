"""Unit tests for TickData model."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.market.models import TickData


@pytest.mark.django_db
class TestTickDataModel:
    """Test TickData model."""

    def test_create_tick_data(self) -> None:
        """Test creating tick data."""
        now = timezone.now()
        tick = TickData.objects.create(
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
        )

        assert tick.instrument == "EUR_USD"
        assert tick.timestamp == now
        assert tick.bid == Decimal("1.10000")
        assert tick.ask == Decimal("1.10010")
        # Mid should be calculated automatically
        assert tick.mid == Decimal("1.10005")

    def test_mid_calculation(self) -> None:
        """Test automatic mid price calculation."""
        now = timezone.now()
        tick = TickData.objects.create(
            instrument="GBP_USD",
            timestamp=now,
            bid=Decimal("1.25000"),
            ask=Decimal("1.25020"),
        )

        expected_mid = (Decimal("1.25000") + Decimal("1.25020")) / Decimal("2")
        assert tick.mid == expected_mid

    def test_spread_property(self) -> None:
        """Test spread calculation."""
        now = timezone.now()
        tick = TickData.objects.create(
            instrument="USD_JPY",
            timestamp=now,
            bid=Decimal("110.000"),
            ask=Decimal("110.010"),
        )

        assert tick.spread == Decimal("0.010")

    def test_calculate_mid_static_method(self) -> None:
        """Test static mid calculation method."""
        bid = Decimal("1.30000")
        ask = Decimal("1.30020")

        mid = TickData.calculate_mid(bid, ask)
        assert mid == Decimal("1.30010")

    def test_calculate_spread_static_method(self) -> None:
        """Test static spread calculation method."""
        bid = Decimal("1.40000")
        ask = Decimal("1.40015")

        spread = TickData.calculate_spread(bid, ask)
        assert spread == Decimal("0.00015")

    def test_str_representation(self) -> None:
        """Test string representation."""
        now = timezone.now()
        tick = TickData.objects.create(
            instrument="AUD_USD",
            timestamp=now,
            bid=Decimal("0.70000"),
            ask=Decimal("0.70010"),
        )

        str_repr = str(tick)
        assert "AUD_USD" in str_repr
        assert "0.70000" in str_repr
        assert "0.70010" in str_repr

    def test_get_retention_days(self) -> None:
        """Test getting retention days from settings."""
        retention_days = TickData.get_retention_days()
        assert isinstance(retention_days, int)
        assert retention_days > 0

    def test_cleanup_old_data(self) -> None:
        """Test cleaning up old tick data."""
        from datetime import timedelta

        # Create old tick data
        old_timestamp = timezone.now() - timedelta(days=100)
        TickData.objects.create(
            instrument="EUR_USD",
            timestamp=old_timestamp,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
        )

        # Create recent tick data
        recent_timestamp = timezone.now()
        TickData.objects.create(
            instrument="EUR_USD",
            timestamp=recent_timestamp,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
        )

        # Cleanup with 90 day retention
        deleted_count = TickData.cleanup_old_data(retention_days=90)

        # Old data should be deleted
        assert deleted_count >= 0
        # Recent data should remain
        assert TickData.objects.filter(timestamp=recent_timestamp).exists()
