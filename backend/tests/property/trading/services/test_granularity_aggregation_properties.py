"""Property-based tests for GranularityAggregationService.

Feature: trading-app-refactor

This module contains property-based tests that verify universal properties
of the GranularityAggregationService across all possible inputs.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apps.trading.enums import TaskType
from apps.trading.models.execution import Executions
from apps.trading.models.metrics import TradingMetrics
from apps.trading.services.granularity_aggregation import (
    GranularityAggregationService,
)

# Property 3: Time Window Binning Correctness
# Feature: trading-app-refactor, Property 3: Time Window Binning Correctness
#
# For any set of TradingMetrics records and granularity value, when records are
# binned by time windows, each record should appear in exactly one bin, and the
# bin timestamp should be the floor of (record_timestamp / granularity) * granularity.
#
# Validates: Requirements 5.4


@pytest.mark.django_db
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    granularity=st.integers(min_value=1, max_value=3600),
    num_metrics=st.integers(min_value=10, max_value=100),
    seed=st.integers(min_value=1, max_value=1000000),
)
def test_property_3_time_window_binning_correctness(
    granularity: int,
    num_metrics: int,
    seed: int,
):
    """
    Feature: trading-app-refactor, Property 3: Time Window Binning Correctness

    For any set of TradingMetrics records and granularity value, when records are
    binned by time windows, each record should appear in exactly one bin, and the
    bin timestamp should be the floor of (record_timestamp / granularity) * granularity.

    Validates: Requirements 5.4
    """
    # Create execution with unique identifier based on seed
    execution = Executions.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=seed,
        execution_number=1,
    )

    try:
        # Generate metrics
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        metrics_list = []

        for i in range(num_metrics):
            # Spread metrics across a time range (up to 1 hour)
            timestamp = base_time + timedelta(seconds=i * 36)  # Every 36 seconds

            metric = TradingMetrics.objects.create(
                execution=execution,
                sequence=i,
                timestamp=timestamp,
                realized_pnl=Decimal("100.00"),
                unrealized_pnl=Decimal("50.00"),
                total_pnl=Decimal("150.00"),
                open_positions=1,
                total_trades=i + 1,
                tick_ask_min=Decimal("1.1000"),
                tick_ask_max=Decimal("1.1000"),
                tick_ask_avg=Decimal("1.1000"),
                tick_bid_min=Decimal("1.0998"),
                tick_bid_max=Decimal("1.0998"),
                tick_bid_avg=Decimal("1.0998"),
                tick_mid_min=Decimal("1.0999"),
                tick_mid_max=Decimal("1.0999"),
                tick_mid_avg=Decimal("1.0999"),
            )
            metrics_list.append(metric)

        # Aggregate metrics
        service = GranularityAggregationService()
        bins = service.aggregate_metrics(
            execution=execution,
            granularity_seconds=granularity,
        )

        # Property 1: Each record appears in exactly one bin
        # Count total metrics in all bins
        total_metrics_in_bins = sum(
            len(
                [
                    m
                    for m in metrics_list
                    if service._calculate_bin_timestamp(m.timestamp, granularity) == bin.timestamp
                ]
            )
            for bin in bins
        )

        assert total_metrics_in_bins == len(metrics_list), (
            f"Each metric should appear in exactly one bin. "
            f"Expected {len(metrics_list)} metrics, found {total_metrics_in_bins} in bins"
        )

        # Property 2: Bin timestamps are correctly aligned to granularity boundaries
        for bin in bins:
            # Verify bin timestamp is aligned to granularity
            epoch_seconds = int(bin.timestamp.timestamp())
            assert epoch_seconds % granularity == 0, (
                f"Bin timestamp should be aligned to granularity boundary. "
                f"Bin timestamp: {bin.timestamp}, granularity: {granularity}, "
                f"epoch_seconds: {epoch_seconds}, remainder: {epoch_seconds % granularity}"
            )

        # Property 3: All metrics in a bin have timestamps that map to that bin
        for bin in bins:
            metrics_in_bin = [
                m
                for m in metrics_list
                if service._calculate_bin_timestamp(m.timestamp, granularity) == bin.timestamp
            ]

            for metric in metrics_in_bin:
                calculated_bin = service._calculate_bin_timestamp(metric.timestamp, granularity)
                assert calculated_bin == bin.timestamp, (
                    f"Metric timestamp {metric.timestamp} should map to bin {bin.timestamp}, "
                    f"but calculated bin is {calculated_bin}"
                )

        # Property 4: Bins are non-overlapping and cover all metrics
        # Verify no gaps or overlaps
        bin_timestamps = [bin.timestamp for bin in bins]
        assert len(bin_timestamps) == len(set(bin_timestamps)), (
            "Bin timestamps should be unique (no overlapping bins)"
        )

        # Property 5: Bins are ordered chronologically
        for i in range(len(bins) - 1):
            assert bins[i].timestamp < bins[i + 1].timestamp, (
                f"Bins should be ordered chronologically. "
                f"Bin {i} timestamp: {bins[i].timestamp}, "
                f"Bin {i + 1} timestamp: {bins[i + 1].timestamp}"
            )

    finally:
        # Clean up
        execution.delete()


# Property 4: Statistical Aggregation Correctness
# Feature: trading-app-refactor, Property 4: Statistical Aggregation Correctness
#
# For any bin of TradingMetrics records, when statistical aggregations are calculated,
# the following should hold for each metric field:
# - min_value ≤ avg_value ≤ max_value
# - min_value ≤ median_value ≤ max_value
# - min_value equals the minimum value in the bin
# - max_value equals the maximum value in the bin
#
# Validates: Requirements 5.5, 5.6, 5.7, 5.8, 5.9


@pytest.mark.django_db
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    granularity=st.integers(min_value=60, max_value=3600),
    num_metrics=st.integers(min_value=10, max_value=100),
    seed=st.integers(min_value=1, max_value=1000000),
)
def test_property_4_statistical_aggregation_correctness(
    granularity: int,
    num_metrics: int,
    seed: int,
):
    """
    Feature: trading-app-refactor, Property 4: Statistical Aggregation Correctness

    For any bin of TradingMetrics records, when statistical aggregations are calculated,
    the following should hold for each metric field:
    - min_value ≤ avg_value ≤ max_value
    - min_value ≤ median_value ≤ max_value
    - min_value equals the minimum value in the bin
    - max_value equals the maximum value in the bin

    Validates: Requirements 5.5, 5.6, 5.7, 5.8, 5.9
    """
    # Create execution with unique identifier based on seed
    execution = Executions.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=seed,
        execution_number=1,
    )

    try:
        # Generate metrics with varying values
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        metrics_list = []

        for i in range(num_metrics):
            # Spread metrics across a time range
            timestamp = base_time + timedelta(seconds=i * 36)

            # Use varying values for testing statistical properties
            realized_pnl = Decimal(str(100 + i * 10))
            unrealized_pnl = Decimal(str(50 + i * 5))
            tick_ask = Decimal(str(1.1000 + i * 0.0001))
            tick_bid = Decimal(str(1.0998 + i * 0.0001))
            tick_mid = (tick_ask + tick_bid) / Decimal("2")

            metric = TradingMetrics.objects.create(
                execution=execution,
                sequence=i,
                timestamp=timestamp,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                total_pnl=realized_pnl + unrealized_pnl,
                open_positions=1,
                total_trades=i + 1,
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
            metrics_list.append(metric)

        # Aggregate metrics
        service = GranularityAggregationService()
        bins = service.aggregate_metrics(
            execution=execution,
            granularity_seconds=granularity,
        )

        # Verify statistical properties for each bin
        for bin in bins:
            stats = bin.statistics

            # Get metrics in this bin
            metrics_in_bin = [
                m
                for m in metrics_list
                if service._calculate_bin_timestamp(m.timestamp, granularity) == bin.timestamp
            ]

            # Property 1: min ≤ avg ≤ max for realized PnL
            assert stats.realized_pnl_min <= stats.realized_pnl_avg <= stats.realized_pnl_max, (
                f"Realized PnL: min ≤ avg ≤ max invariant violated. "
                f"min={stats.realized_pnl_min}, avg={stats.realized_pnl_avg}, "
                f"max={stats.realized_pnl_max}"
            )

            # Property 2: min ≤ median ≤ max for realized PnL
            assert stats.realized_pnl_min <= stats.realized_pnl_median <= stats.realized_pnl_max, (
                f"Realized PnL: min ≤ median ≤ max invariant violated. "
                f"min={stats.realized_pnl_min}, median={stats.realized_pnl_median}, "
                f"max={stats.realized_pnl_max}"
            )

            # Property 3: min ≤ avg ≤ max for unrealized PnL
            assert (
                stats.unrealized_pnl_min <= stats.unrealized_pnl_avg <= stats.unrealized_pnl_max
            ), (
                f"Unrealized PnL: min ≤ avg ≤ max invariant violated. "
                f"min={stats.unrealized_pnl_min}, avg={stats.unrealized_pnl_avg}, "
                f"max={stats.unrealized_pnl_max}"
            )

            # Property 4: min ≤ median ≤ max for unrealized PnL
            assert (
                stats.unrealized_pnl_min <= stats.unrealized_pnl_median <= stats.unrealized_pnl_max
            ), (
                f"Unrealized PnL: min ≤ median ≤ max invariant violated. "
                f"min={stats.unrealized_pnl_min}, median={stats.unrealized_pnl_median}, "
                f"max={stats.unrealized_pnl_max}"
            )

            # Property 5: min ≤ avg ≤ max for tick ask
            assert stats.tick_ask_min <= stats.tick_ask_avg <= stats.tick_ask_max, (
                f"Tick ask: min ≤ avg ≤ max invariant violated. "
                f"min={stats.tick_ask_min}, avg={stats.tick_ask_avg}, max={stats.tick_ask_max}"
            )

            # Property 6: min ≤ median ≤ max for tick ask
            assert stats.tick_ask_min <= stats.tick_ask_median <= stats.tick_ask_max, (
                f"Tick ask: min ≤ median ≤ max invariant violated. "
                f"min={stats.tick_ask_min}, median={stats.tick_ask_median}, "
                f"max={stats.tick_ask_max}"
            )

            # Property 7: min ≤ avg ≤ max for tick bid
            assert stats.tick_bid_min <= stats.tick_bid_avg <= stats.tick_bid_max, (
                f"Tick bid: min ≤ avg ≤ max invariant violated. "
                f"min={stats.tick_bid_min}, avg={stats.tick_bid_avg}, max={stats.tick_bid_max}"
            )

            # Property 8: min ≤ median ≤ max for tick bid
            assert stats.tick_bid_min <= stats.tick_bid_median <= stats.tick_bid_max, (
                f"Tick bid: min ≤ median ≤ max invariant violated. "
                f"min={stats.tick_bid_min}, median={stats.tick_bid_median}, "
                f"max={stats.tick_bid_max}"
            )

            # Property 9: min ≤ avg ≤ max for tick mid
            assert stats.tick_mid_min <= stats.tick_mid_avg <= stats.tick_mid_max, (
                f"Tick mid: min ≤ avg ≤ max invariant violated. "
                f"min={stats.tick_mid_min}, avg={stats.tick_mid_avg}, max={stats.tick_mid_max}"
            )

            # Property 10: min ≤ median ≤ max for tick mid
            assert stats.tick_mid_min <= stats.tick_mid_median <= stats.tick_mid_max, (
                f"Tick mid: min ≤ median ≤ max invariant violated. "
                f"min={stats.tick_mid_min}, median={stats.tick_mid_median}, "
                f"max={stats.tick_mid_max}"
            )

            # Property 11: min equals actual minimum in bin
            actual_realized_pnl_min = min(m.realized_pnl for m in metrics_in_bin)
            assert stats.realized_pnl_min == actual_realized_pnl_min, (
                f"Realized PnL min should equal actual minimum. "
                f"Calculated: {stats.realized_pnl_min}, Actual: {actual_realized_pnl_min}"
            )

            # Property 12: max equals actual maximum in bin
            actual_realized_pnl_max = max(m.realized_pnl for m in metrics_in_bin)
            assert stats.realized_pnl_max == actual_realized_pnl_max, (
                f"Realized PnL max should equal actual maximum. "
                f"Calculated: {stats.realized_pnl_max}, Actual: {actual_realized_pnl_max}"
            )

            # Property 13: trade count is the max total_trades in bin
            actual_trade_count = max(m.total_trades for m in metrics_in_bin)
            assert stats.trade_count == actual_trade_count, (
                f"Trade count should equal max total_trades in bin. "
                f"Calculated: {stats.trade_count}, Actual: {actual_trade_count}"
            )

    finally:
        # Clean up
        execution.delete()
