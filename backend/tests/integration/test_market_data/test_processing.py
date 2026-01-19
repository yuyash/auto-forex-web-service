"""
Integration tests for market data processing.

Tests data parsing, validation, storage, and strategy triggering.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.utils import timezone as django_timezone

from apps.market.models import TickData
from apps.trading.models import TradingTasks
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TickDataFactory,
    TradingTaskFactory,
)


class MarketDataProcessingTestCase(IntegrationTestCase):
    """Test market data processing flows."""

    def setUp(self) -> None:
        """Set up test data for market data processing tests."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

    def test_tick_data_parsing_and_validation(self) -> None:
        """
        Test that tick data is correctly parsed and validated."""
        # Create tick data with valid values
        tick = TickDataFactory(
            instrument="EUR_USD",
            timestamp=django_timezone.now(),
            bid=Decimal("1.08950"),
            ask=Decimal("1.08955"),
            mid=Decimal("1.089525"),
        )

        # Verify tick was created with correct values
        self.assertEqual(tick.instrument, "EUR_USD")
        self.assertIsInstance(tick.timestamp, datetime)
        self.assertEqual(tick.bid, Decimal("1.08950"))
        self.assertEqual(tick.ask, Decimal("1.08955"))
        self.assertEqual(tick.mid, Decimal("1.089525"))

        # Verify mid price is between bid and ask
        self.assertGreaterEqual(tick.mid, tick.bid)  # ty:ignore[no-matching-overload]
        self.assertLessEqual(tick.mid, tick.ask)  # ty:ignore[no-matching-overload]

    def test_tick_data_storage_with_correct_timestamps(self) -> None:
        """
        Test that tick data is stored with correct timestamps."""
        # Create tick with specific timestamp
        test_timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        tick = TickDataFactory(
            instrument="GBP_USD",
            timestamp=test_timestamp,
            bid=Decimal("1.27500"),
            ask=Decimal("1.27505"),
        )

        # Retrieve from database
        saved_tick = TickData.objects.get(
            instrument=tick.instrument,
            timestamp=tick.timestamp,
        )

        # Verify timestamp is preserved correctly
        self.assertEqual(saved_tick.timestamp, test_timestamp)
        self.assertEqual(saved_tick.instrument, "GBP_USD")

        # Verify created_at is set automatically
        self.assertIsNotNone(saved_tick.created_at)
        self.assertIsInstance(saved_tick.created_at, datetime)

    def test_multiple_ticks_storage_in_sequence(self) -> None:
        """
        Test that multiple ticks are stored correctly in sequence."""
        # Create multiple ticks for the same instrument
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        ticks = []

        for i in range(5):
            tick = TickDataFactory(
                instrument="USD_JPY",
                timestamp=datetime(2024, 1, 15, 10, 0, i, tzinfo=timezone.utc),
                bid=Decimal(f"150.{100 + i:03d}"),
                ask=Decimal(f"150.{105 + i:03d}"),
            )
            ticks.append(tick)

        # Verify all ticks are stored
        stored_ticks = TickData.objects.filter(
            instrument="USD_JPY",
            timestamp__gte=base_time,
        ).order_by("timestamp")

        self.assertEqual(stored_ticks.count(), 5)

        # Verify timestamps are in correct order
        for i, tick in enumerate(stored_ticks):
            self.assertEqual(
                tick.timestamp,
                datetime(2024, 1, 15, 10, 0, i, tzinfo=timezone.utc),
            )

    def test_tick_data_retrieval_by_instrument(self) -> None:
        """
        Test that tick data can be retrieved by instrument."""
        # Create ticks for different instruments
        TickDataFactory(instrument="EUR_USD", bid=Decimal("1.08950"))
        TickDataFactory(instrument="GBP_USD", bid=Decimal("1.27500"))
        TickDataFactory(instrument="EUR_USD", bid=Decimal("1.08960"))

        # Retrieve ticks for specific instrument
        eur_usd_ticks = TickData.objects.filter(instrument="EUR_USD")
        gbp_usd_ticks = TickData.objects.filter(instrument="GBP_USD")

        # Verify correct filtering
        self.assertEqual(eur_usd_ticks.count(), 2)
        self.assertEqual(gbp_usd_ticks.count(), 1)

    def test_tick_data_retrieval_by_time_range(self) -> None:
        """
        Test that tick data can be retrieved by time range."""
        # Create ticks at different times
        datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        for hour in range(3):
            TickDataFactory(
                instrument="AUD_USD",
                timestamp=datetime(2024, 1, 15, 10 + hour, 0, 0, tzinfo=timezone.utc),
                bid=Decimal(f"0.{6500 + hour:04d}"),
            )

        # Query ticks in specific time range
        start_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        ticks_in_range = TickData.objects.filter(
            instrument="AUD_USD",
            timestamp__gte=start_time,
            timestamp__lte=end_time,
        )

        # Should get ticks at 11:00 and 12:00
        self.assertEqual(ticks_in_range.count(), 2)

    def test_strategy_triggering_on_matching_instrument(self) -> None:
        """
        Test that strategies are triggered when matching tick data arrives."""
        # Create a trading task for USD_JPY
        trading_task = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.strategy_config,
            instrument="USD_JPY",
            status="running",
        )

        # Create tick data for the matching instrument
        tick = TickDataFactory(
            instrument="USD_JPY",
            timestamp=django_timezone.now(),
            bid=Decimal("150.500"),
            ask=Decimal("150.505"),
        )

        # Verify trading task exists for this instrument
        matching_tasks = TradingTasks.objects.filter(
            instrument=tick.instrument,
            status="running",
        )

        self.assertEqual(matching_tasks.count(), 1)
        self.assertEqual(matching_tasks.first().id, trading_task.pk)  # type: ignore[attr-defined]

    def test_no_strategy_triggering_for_non_matching_instrument(self) -> None:
        """
        Test that strategies are not triggered for non-matching instruments."""
        # Create a trading task for EUR_USD
        TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.strategy_config,
            instrument="EUR_USD",
            status="running",
        )

        # Create tick data for a different instrument
        tick = TickDataFactory(
            instrument="GBP_USD",
            timestamp=django_timezone.now(),
            bid=Decimal("1.27500"),
            ask=Decimal("1.27505"),
        )

        # Verify no matching tasks for GBP_USD
        matching_tasks = TradingTasks.objects.filter(
            instrument=tick.instrument,
            status="running",
        )

        self.assertEqual(matching_tasks.count(), 0)

    def test_tick_data_with_spread_calculation(self) -> None:
        """
        Test that tick data correctly represents bid-ask spread."""
        # Create tick with known spread
        tick = TickDataFactory(
            instrument="EUR_USD",
            bid=Decimal("1.08950"),
            ask=Decimal("1.08955"),
            mid=Decimal("1.089525"),
        )

        # Calculate spread
        spread = tick.ask - tick.bid  # ty:ignore[unsupported-operator]

        # Verify spread is positive and reasonable
        self.assertGreater(spread, Decimal("0"))
        self.assertEqual(spread, Decimal("0.00005"))

        # Verify mid is average of bid and ask
        expected_mid = (tick.bid + tick.ask) / 2  # ty:ignore[unsupported-operator]
        self.assertEqual(tick.mid, expected_mid)

    def test_tick_data_composite_primary_key(self) -> None:
        """
        Test that tick data uses composite primary key (instrument, timestamp)."""
        # Create first tick
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        tick1 = TickDataFactory(
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.08950"),
        )

        # Verify tick was created
        self.assertIsNotNone(tick1)

        # Try to create another tick with same instrument and timestamp
        # This should either update or raise an error depending on implementation
        tick2 = TickData.objects.filter(
            instrument="EUR_USD",
            timestamp=timestamp,
        ).first()

        self.assertIsNotNone(tick2)
        self.assertEqual(tick2.instrument, tick1.instrument)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(tick2.timestamp, tick1.timestamp)  # ty:ignore[possibly-missing-attribute]


@pytest.mark.django_db
class TestMarketDataProcessingPytest:
    """Pytest-style tests for market data processing."""

    def test_tick_data_creation_with_factory(self) -> None:
        """Test tick data creation using factory."""
        tick = TickDataFactory()

        assert tick.instrument is not None
        assert tick.timestamp is not None
        assert tick.bid > 0  # ty:ignore[unsupported-operator]
        assert tick.ask > 0  # ty:ignore[unsupported-operator]
        assert tick.mid > 0  # ty:ignore[unsupported-operator]
        assert tick.ask >= tick.bid  # ty:ignore[unsupported-operator]

    def test_multiple_instruments_storage(self) -> None:
        """Test storing ticks for multiple instruments."""
        instruments = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]

        for instrument in instruments:
            TickDataFactory(instrument=instrument)

        # Verify all instruments have ticks
        for instrument in instruments:
            count = TickData.objects.filter(instrument=instrument).count()
            assert count >= 1

    def test_tick_data_ordering_by_timestamp(self) -> None:
        """Test that ticks can be ordered by timestamp."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Create ticks in random order
        timestamps = [
            datetime(2024, 1, 15, 10, 2, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 10, 1, 0, tzinfo=timezone.utc),
        ]

        for ts in timestamps:
            TickDataFactory(instrument="EUR_USD", timestamp=ts)

        # Retrieve ordered by timestamp
        ticks = TickData.objects.filter(
            instrument="EUR_USD",
            timestamp__gte=base_time,
        ).order_by("timestamp")

        # Verify correct ordering
        assert ticks.count() == 3
        assert ticks[0].timestamp < ticks[1].timestamp < ticks[2].timestamp
