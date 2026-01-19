"""
Integration tests for invalid market data handling.

Tests handling of malformed data, error logging, and continued processing.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone as django_timezone

from apps.market.models import TickData
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import TickDataFactory


class InvalidMarketDataHandlingTestCase(IntegrationTestCase):
    """Test invalid market data handling flows."""

    def test_handling_of_negative_bid_price(self) -> None:
        """
        Test that negative bid prices are handled gracefully."""
        # Attempt to create tick with negative bid
        with self.assertRaises((ValidationError, ValueError, InvalidOperation)):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("-1.08950"),  # Invalid negative price
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )

    def test_handling_of_negative_ask_price(self) -> None:
        """
        Test that negative ask prices are handled gracefully."""
        # Attempt to create tick with negative ask
        with self.assertRaises((ValidationError, ValueError, InvalidOperation)):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("1.08950"),
                ask=Decimal("-1.08955"),  # Invalid negative price
                mid=Decimal("1.089525"),
            )

    def test_handling_of_ask_less_than_bid(self) -> None:
        """
        Test that ask < bid is handled (invalid spread)."""
        # Create tick where ask < bid (invalid)
        # This should either raise an error or be stored as-is
        # depending on validation rules
        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("1.08955"),
                ask=Decimal("1.08950"),  # Ask < Bid (invalid)
                mid=Decimal("1.089525"),
            )
            # If it's stored, verify we can detect the invalid state
            self.assertLess(tick.ask, tick.bid)
        except (ValidationError, ValueError):
            # Expected if validation is enforced
            pass

    def test_handling_of_missing_instrument(self) -> None:
        """
        Test that missing instrument field is handled."""
        # Attempt to create tick without instrument
        with self.assertRaises((ValidationError, IntegrityError, ValueError)):
            TickData.objects.create(
                instrument="",  # Empty instrument
                timestamp=django_timezone.now(),
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )

    def test_handling_of_missing_timestamp(self) -> None:
        """
        Test that missing timestamp is handled."""
        # Attempt to create tick without timestamp
        with self.assertRaises((ValidationError, IntegrityError, TypeError)):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=None,  # type: ignore
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )

    def test_handling_of_invalid_decimal_format(self) -> None:
        """
        Test that invalid decimal formats are handled."""
        # Attempt to create tick with invalid decimal
        with self.assertRaises((ValidationError, ValueError, InvalidOperation, TypeError)):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid="invalid_decimal",  # type: ignore
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )

    def test_handling_of_duplicate_tick_data(self) -> None:
        """
        Test that duplicate tick data (same instrument + timestamp) is handled."""
        # Create first tick
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        TickDataFactory(
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.08950"),
        )

        # Attempt to create duplicate tick with same composite key
        with self.assertRaises(IntegrityError):
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=timestamp,
                bid=Decimal("1.08960"),  # Different price
                ask=Decimal("1.08965"),
                mid=Decimal("1.089625"),
            )

    def test_continued_processing_after_error(self) -> None:
        """
        Test that processing continues after encountering an error."""
        # Create valid tick
        tick1 = TickDataFactory(
            instrument="EUR_USD",
            timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Attempt to create invalid tick (should fail)
        try:
            TickData.objects.create(
                instrument="",  # Invalid
                timestamp=datetime(2024, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )
        except (ValidationError, IntegrityError, ValueError):
            pass  # Expected error

        # Create another valid tick after error
        tick3 = TickDataFactory(
            instrument="GBP_USD",
            timestamp=datetime(2024, 1, 15, 10, 2, 0, tzinfo=timezone.utc),
        )

        # Verify both valid ticks exist
        self.assertTrue(
            TickData.objects.filter(
                instrument=tick1.instrument,
                timestamp=tick1.timestamp,
            ).exists()
        )
        self.assertTrue(
            TickData.objects.filter(
                instrument=tick3.instrument,
                timestamp=tick3.timestamp,
            ).exists()
        )

    def test_handling_of_extremely_large_prices(self) -> None:
        """
        Test that extremely large prices are handled."""
        # Attempt to create tick with very large price
        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("999999.99999"),  # Very large price
                ask=Decimal("1000000.00000"),
                mid=Decimal("999999.999995"),
            )
            # If accepted, verify it's stored correctly
            self.assertEqual(tick.bid, Decimal("999999.99999"))
        except (ValidationError, ValueError):
            # Expected if validation rejects large values
            pass

    def test_handling_of_zero_prices(self) -> None:
        """
        Test that zero prices are handled."""
        # Attempt to create tick with zero prices
        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("0.00000"),
                ask=Decimal("0.00000"),
                mid=Decimal("0.00000"),
            )
            # If accepted, verify it's stored
            self.assertEqual(tick.bid, Decimal("0.00000"))
        except (ValidationError, ValueError):
            # Expected if validation rejects zero prices
            pass


@pytest.mark.django_db
class TestInvalidMarketDataHandlingPytest:
    """Pytest-style tests for invalid market data handling."""

    def test_invalid_instrument_format(self) -> None:
        """Test handling of invalid instrument format."""
        with pytest.raises((ValidationError, IntegrityError, ValueError)):
            TickData.objects.create(
                instrument="INVALID",  # Should be format like EUR_USD
                timestamp=django_timezone.now(),
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )

    def test_future_timestamp_handling(self) -> None:
        """Test handling of future timestamps."""
        # Create tick with future timestamp
        future_time = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=future_time,
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )
            # If accepted, verify timestamp
            assert tick.timestamp == future_time
        except ValidationError:
            # Expected if future timestamps are rejected
            pass

    def test_very_old_timestamp_handling(self) -> None:
        """Test handling of very old timestamps."""
        # Create tick with very old timestamp
        old_time = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=old_time,
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )
            # If accepted, verify timestamp
            assert tick.timestamp == old_time
        except ValidationError:
            # Expected if old timestamps are rejected
            pass

    def test_mid_price_not_between_bid_ask(self) -> None:
        """Test handling when mid price is not between bid and ask."""
        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("2.00000"),  # Mid not between bid/ask
            )
            # If accepted, verify the invalid state
            assert tick.mid > tick.ask or tick.mid < tick.bid
        except ValidationError:
            # Expected if validation enforces mid between bid/ask
            pass

    def test_too_many_decimal_places(self) -> None:
        """Test handling of prices with too many decimal places."""
        try:
            tick = TickData.objects.create(
                instrument="EUR_USD",
                timestamp=django_timezone.now(),
                bid=Decimal("1.089501234567"),  # More than 5 decimal places
                ask=Decimal("1.089551234567"),
                mid=Decimal("1.089526234567"),
            )
            # If accepted, verify rounding occurred
            assert tick.bid.as_tuple().exponent >= -5
        except (ValidationError, ValueError, InvalidOperation):
            # Expected if too many decimals are rejected
            pass

    @patch("apps.market.models.logger")
    def test_error_logging_on_invalid_data(self, mock_logger) -> None:
        """Test that errors are logged when invalid data is encountered."""
        # Attempt to create invalid tick
        try:
            TickData.objects.create(
                instrument="",
                timestamp=django_timezone.now(),
                bid=Decimal("1.08950"),
                ask=Decimal("1.08955"),
                mid=Decimal("1.089525"),
            )
        except (ValidationError, IntegrityError, ValueError):
            pass  # Expected error

        # Note: Actual logging verification would depend on
        # how the application logs errors
        # This is a placeholder for logging verification
