"""Unit tests for GranularityAggregationService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.test import TestCase

from apps.trading.enums import TaskType
from apps.trading.models.execution import Executions
from apps.trading.models.metrics import TradingMetrics
from apps.trading.services.granularity_aggregation import (
    GranularityAggregationService,
)


class TestGranularityAggregationService(TestCase):
    """Test suite for GranularityAggregationService.

    Tests:
    - Aggregation with different granularities (1s, 60s, 300s, 3600s)
    - Edge cases: empty executions, single tick, thousands of ticks
    - Statistical calculations accuracy
    - Bin boundary conditions
    """

    def setUp(self):
        """Set up test fixtures."""
        self.service = GranularityAggregationService()

        # Create test execution
        self.execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

        # Base timestamp for tests
        self.base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    def _create_metrics(
        self,
        sequence: int,
        timestamp: datetime,
        realized_pnl: Decimal = Decimal("100.00"),
        unrealized_pnl: Decimal = Decimal("50.00"),
        tick_ask: Decimal = Decimal("1.1000"),
        tick_bid: Decimal = Decimal("1.0998"),
        tick_mid: Decimal = Decimal("1.0999"),
    ) -> TradingMetrics:
        """Helper to create TradingMetrics for testing."""
        return TradingMetrics.objects.create(
            execution=self.execution,
            sequence=sequence,
            timestamp=timestamp,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=realized_pnl + unrealized_pnl,
            open_positions=1,
            total_trades=sequence + 1,
            tick_ask_min=tick_ask,
            tick_ask_max=tick_ask,
            tick_ask_avg=tick_ask,
            tick_bid_min=tick_bid,
            tick_bid_max=tick_bid,
            tick_bid_avg=tick_bid,
            tick_mid_min=tick_mid,
            tick_mid_max=tick_mid,
            tick_mid_avg=tick_mid,
        )

    def test_aggregate_metrics_1_second_granularity(self):
        """Test aggregation with 1-second granularity."""
        # Create metrics at different seconds
        self._create_metrics(0, self.base_time, Decimal("100.00"))
        self._create_metrics(1, self.base_time + timedelta(seconds=1), Decimal("110.00"))
        self._create_metrics(2, self.base_time + timedelta(seconds=2), Decimal("120.00"))

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=1,
        )

        # Should have 3 bins (one per second)
        assert len(bins) == 3

        # Verify first bin
        assert bins[0].timestamp == self.base_time
        assert bins[0].statistics.realized_pnl_min == Decimal("100.00")
        assert bins[0].statistics.realized_pnl_max == Decimal("100.00")
        assert bins[0].statistics.realized_pnl_avg == Decimal("100.00")

    def test_aggregate_metrics_60_second_granularity(self):
        """Test aggregation with 60-second (1-minute) granularity."""
        # Create metrics across 2 minutes
        for i in range(120):  # 120 seconds = 2 minutes
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                Decimal(str(100 + i)),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        # Should have 2 bins (one per minute)
        assert len(bins) == 2

        # First bin: seconds 0-59
        assert bins[0].timestamp == self.base_time
        assert bins[0].statistics.realized_pnl_min == Decimal("100")
        assert bins[0].statistics.realized_pnl_max == Decimal("159")

        # Second bin: seconds 60-119
        assert bins[1].timestamp == self.base_time + timedelta(seconds=60)
        assert bins[1].statistics.realized_pnl_min == Decimal("160")
        assert bins[1].statistics.realized_pnl_max == Decimal("219")

    def test_aggregate_metrics_300_second_granularity(self):
        """Test aggregation with 300-second (5-minute) granularity."""
        # Create metrics across 10 minutes
        for i in range(600):  # 600 seconds = 10 minutes
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                Decimal(str(100 + i)),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=300,
        )

        # Should have 2 bins (one per 5 minutes)
        assert len(bins) == 2

        # First bin: seconds 0-299
        assert bins[0].timestamp == self.base_time
        assert bins[0].statistics.realized_pnl_min == Decimal("100")
        assert bins[0].statistics.realized_pnl_max == Decimal("399")

        # Second bin: seconds 300-599
        assert bins[1].timestamp == self.base_time + timedelta(seconds=300)
        assert bins[1].statistics.realized_pnl_min == Decimal("400")
        assert bins[1].statistics.realized_pnl_max == Decimal("699")

    def test_aggregate_metrics_3600_second_granularity(self):
        """Test aggregation with 3600-second (1-hour) granularity."""
        # Create metrics across 2 hours
        for i in range(0, 7200, 60):  # Every minute for 2 hours
            self._create_metrics(
                i // 60,
                self.base_time + timedelta(seconds=i),
                Decimal(str(100 + i)),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=3600,
        )

        # Should have 2 bins (one per hour)
        assert len(bins) == 2

        # First bin: 0-3599 seconds
        assert bins[0].timestamp == self.base_time

        # Second bin: 3600-7199 seconds
        assert bins[1].timestamp == self.base_time + timedelta(seconds=3600)

    def test_edge_case_single_tick(self):
        """Test aggregation with only one tick."""
        self._create_metrics(
            0,
            self.base_time,
            Decimal("100.00"),
            Decimal("50.00"),
        )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        # Should have 1 bin
        assert len(bins) == 1

        # All statistics should equal the single value
        assert bins[0].statistics.realized_pnl_min == Decimal("100.00")
        assert bins[0].statistics.realized_pnl_max == Decimal("100.00")
        assert bins[0].statistics.realized_pnl_avg == Decimal("100.00")
        assert bins[0].statistics.realized_pnl_median == Decimal("100.00")

    def test_edge_case_empty_execution(self):
        """Test error handling when execution has no metrics."""
        # Create empty execution
        empty_execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=2,
            execution_number=1,
        )

        with pytest.raises(ValueError, match="No TradingMetrics found"):
            self.service.aggregate_metrics(
                execution=empty_execution,
                granularity_seconds=60,
            )

    def test_edge_case_thousands_of_ticks(self):
        """Test aggregation with thousands of ticks."""
        # Create 10,000 ticks (one per second for ~2.7 hours)
        for i in range(10000):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                Decimal(str(100 + i * 0.1)),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=300,  # 5-minute bins
        )

        # 10,000 seconds / 300 seconds per bin = 34 bins (rounded up)
        assert len(bins) == 34

        # Verify bins are ordered
        for i in range(len(bins) - 1):
            assert bins[i].timestamp < bins[i + 1].timestamp

    def test_statistical_calculations_accuracy(self):
        """Test accuracy of min/max/avg/median calculations."""
        # Create metrics with known values
        values = [Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"), Decimal("500")]

        for i, value in enumerate(values):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                realized_pnl=value,
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,  # All in one bin
        )

        assert len(bins) == 1
        stats = bins[0].statistics

        # Verify statistics
        assert stats.realized_pnl_min == Decimal("100")
        assert stats.realized_pnl_max == Decimal("500")
        assert stats.realized_pnl_avg == Decimal("300")  # (100+200+300+400+500)/5
        assert stats.realized_pnl_median == Decimal("300")  # Middle value

    def test_statistical_calculations_even_count(self):
        """Test median calculation with even number of values."""
        # Create metrics with even count
        values = [Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400")]

        for i, value in enumerate(values):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                realized_pnl=value,
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        assert len(bins) == 1
        stats = bins[0].statistics

        # Median of even count is average of two middle values
        # (200 + 300) / 2 = 250
        assert stats.realized_pnl_median == Decimal("250")

    def test_bin_boundary_conditions(self):
        """Test that bins are correctly aligned to granularity boundaries."""
        # Create metrics at specific times to test boundary alignment
        # Base time: 12:00:00
        # Granularity: 300 seconds (5 minutes)
        # Expected bins: 12:00:00, 12:05:00, 12:10:00

        self._create_metrics(0, self.base_time, Decimal("100"))  # 12:00:00
        self._create_metrics(1, self.base_time + timedelta(seconds=299), Decimal("200"))  # 12:04:59
        self._create_metrics(2, self.base_time + timedelta(seconds=300), Decimal("300"))  # 12:05:00
        self._create_metrics(3, self.base_time + timedelta(seconds=599), Decimal("400"))  # 12:09:59
        self._create_metrics(4, self.base_time + timedelta(seconds=600), Decimal("500"))  # 12:10:00

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=300,
        )

        # Should have 3 bins
        assert len(bins) == 3

        # Verify bin timestamps are aligned to 5-minute boundaries
        assert bins[0].timestamp == self.base_time  # 12:00:00
        assert bins[1].timestamp == self.base_time + timedelta(seconds=300)  # 12:05:00
        assert bins[2].timestamp == self.base_time + timedelta(seconds=600)  # 12:10:00

        # Verify metrics are in correct bins
        assert bins[0].statistics.realized_pnl_min == Decimal("100")
        assert bins[0].statistics.realized_pnl_max == Decimal("200")
        assert bins[1].statistics.realized_pnl_min == Decimal("300")
        assert bins[1].statistics.realized_pnl_max == Decimal("400")
        assert bins[2].statistics.realized_pnl_min == Decimal("500")
        assert bins[2].statistics.realized_pnl_max == Decimal("500")

    def test_tick_statistics_aggregation(self):
        """Test that tick statistics are aggregated correctly."""
        # Create metrics with varying tick prices
        self._create_metrics(
            0,
            self.base_time,
            tick_ask=Decimal("1.1000"),
            tick_bid=Decimal("1.0998"),
            tick_mid=Decimal("1.0999"),
        )
        self._create_metrics(
            1,
            self.base_time + timedelta(seconds=1),
            tick_ask=Decimal("1.1010"),
            tick_bid=Decimal("1.1008"),
            tick_mid=Decimal("1.1009"),
        )
        self._create_metrics(
            2,
            self.base_time + timedelta(seconds=2),
            tick_ask=Decimal("1.0990"),
            tick_bid=Decimal("1.0988"),
            tick_mid=Decimal("1.0989"),
        )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        assert len(bins) == 1
        stats = bins[0].statistics

        # Verify tick ask statistics
        assert stats.tick_ask_min == Decimal("1.0990")
        assert stats.tick_ask_max == Decimal("1.1010")

        # Verify tick bid statistics
        assert stats.tick_bid_min == Decimal("1.0988")
        assert stats.tick_bid_max == Decimal("1.1008")

        # Verify tick mid statistics
        assert stats.tick_mid_min == Decimal("1.0989")
        assert stats.tick_mid_max == Decimal("1.1009")

    def test_trade_count_aggregation(self):
        """Test that trade count is aggregated correctly."""
        # Create metrics with increasing trade counts
        for i in range(5):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        assert len(bins) == 1

        # Trade count should be the max (since total_trades is cumulative)
        # Sequence 0-4 means total_trades 1-5
        assert bins[0].statistics.trade_count == 5

    def test_error_handling_invalid_granularity(self):
        """Test error handling for invalid granularity values."""
        self._create_metrics(0, self.base_time)

        # Zero granularity
        with pytest.raises(ValueError, match="granularity_seconds must be positive"):
            self.service.aggregate_metrics(
                execution=self.execution,
                granularity_seconds=0,
            )

        # Negative granularity
        with pytest.raises(ValueError, match="granularity_seconds must be positive"):
            self.service.aggregate_metrics(
                execution=self.execution,
                granularity_seconds=-60,
            )

    def test_calculate_bin_statistics_empty_list(self):
        """Test error handling when calculating statistics for empty list."""
        with pytest.raises(ValueError, match="metrics list cannot be empty"):
            self.service.calculate_bin_statistics([])

    def test_unrealized_pnl_aggregation(self):
        """Test that unrealized PnL is aggregated correctly."""
        # Create metrics with varying unrealized PnL
        values = [Decimal("-50"), Decimal("0"), Decimal("50"), Decimal("100")]

        for i, value in enumerate(values):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                unrealized_pnl=value,
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        assert len(bins) == 1
        stats = bins[0].statistics

        assert stats.unrealized_pnl_min == Decimal("-50")
        assert stats.unrealized_pnl_max == Decimal("100")
        assert stats.unrealized_pnl_avg == Decimal("25")  # (-50+0+50+100)/4
        assert stats.unrealized_pnl_median == Decimal("25")  # (0+50)/2

    def test_bins_ordered_by_timestamp(self):
        """Test that bins are returned in chronological order."""
        # Create metrics in non-chronological order
        self._create_metrics(2, self.base_time + timedelta(seconds=600))
        self._create_metrics(0, self.base_time)
        self._create_metrics(1, self.base_time + timedelta(seconds=300))

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=300,
        )

        # Bins should be ordered by timestamp
        assert len(bins) == 3
        assert bins[0].timestamp < bins[1].timestamp < bins[2].timestamp

    def test_multiple_metrics_same_bin(self):
        """Test aggregation when multiple metrics fall in the same bin."""
        # Create 10 metrics within the same 60-second bin
        for i in range(10):
            self._create_metrics(
                i,
                self.base_time + timedelta(seconds=i),
                realized_pnl=Decimal(str(100 + i * 10)),
            )

        bins = self.service.aggregate_metrics(
            execution=self.execution,
            granularity_seconds=60,
        )

        assert len(bins) == 1
        stats = bins[0].statistics

        # Verify all 10 metrics were aggregated
        assert stats.realized_pnl_min == Decimal("100")
        assert stats.realized_pnl_max == Decimal("190")
        # Average: (100+110+120+130+140+150+160+170+180+190)/10 = 145
        assert stats.realized_pnl_avg == Decimal("145")

    def test_bin_timestamp_calculation(self):
        """Test that bin timestamps are calculated correctly."""
        # Test various timestamps and granularities
        test_cases = [
            # (timestamp_offset, granularity, expected_bin_offset)
            (0, 60, 0),  # 12:00:00 -> 12:00:00
            (30, 60, 0),  # 12:00:30 -> 12:00:00
            (59, 60, 0),  # 12:00:59 -> 12:00:00
            (60, 60, 60),  # 12:01:00 -> 12:01:00
            (90, 60, 60),  # 12:01:30 -> 12:01:00
            (150, 300, 0),  # 12:02:30 -> 12:00:00
            (300, 300, 300),  # 12:05:00 -> 12:05:00
        ]

        for offset, granularity, expected_offset in test_cases:
            timestamp = self.base_time + timedelta(seconds=offset)
            expected_bin = self.base_time + timedelta(seconds=expected_offset)

            bin_timestamp = self.service._calculate_bin_timestamp(timestamp, granularity)

            assert bin_timestamp == expected_bin, (
                f"Failed for offset={offset}, granularity={granularity}: "
                f"expected {expected_bin}, got {bin_timestamp}"
            )
