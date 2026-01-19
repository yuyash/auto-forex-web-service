"""Granularity aggregation service for binning time-series metrics data."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.models.execution import Executions


@dataclass(frozen=True, slots=True)
class BinStatistics:
    """Statistical summary for a time bin of metrics.

    Contains min/max/avg/median statistics for all metric fields
    within a time window.

    Attributes:
        realized_pnl_min: Minimum realized PnL in bin
        realized_pnl_max: Maximum realized PnL in bin
        realized_pnl_avg: Average realized PnL in bin
        realized_pnl_median: Median realized PnL in bin
        unrealized_pnl_min: Minimum unrealized PnL in bin
        unrealized_pnl_max: Maximum unrealized PnL in bin
        unrealized_pnl_avg: Average unrealized PnL in bin
        unrealized_pnl_median: Median unrealized PnL in bin
        tick_ask_min: Minimum ask price in bin
        tick_ask_max: Maximum ask price in bin
        tick_ask_avg: Average ask price in bin
        tick_ask_median: Median ask price in bin
        tick_bid_min: Minimum bid price in bin
        tick_bid_max: Maximum bid price in bin
        tick_bid_avg: Average bid price in bin
        tick_bid_median: Median bid price in bin
        tick_mid_min: Minimum mid price in bin
        tick_mid_max: Maximum mid price in bin
        tick_mid_avg: Average mid price in bin
        tick_mid_median: Median mid price in bin
        trade_count: Total number of trades in bin
    """

    realized_pnl_min: Decimal
    realized_pnl_max: Decimal
    realized_pnl_avg: Decimal
    realized_pnl_median: Decimal
    unrealized_pnl_min: Decimal
    unrealized_pnl_max: Decimal
    unrealized_pnl_avg: Decimal
    unrealized_pnl_median: Decimal
    tick_ask_min: Decimal
    tick_ask_max: Decimal
    tick_ask_avg: Decimal
    tick_ask_median: Decimal
    tick_bid_min: Decimal
    tick_bid_max: Decimal
    tick_bid_avg: Decimal
    tick_bid_median: Decimal
    tick_mid_min: Decimal
    tick_mid_max: Decimal
    tick_mid_avg: Decimal
    tick_mid_median: Decimal
    trade_count: int


@dataclass(frozen=True, slots=True)
class AggregatedBin:
    """A time bin with aggregated metrics statistics.

    Represents a time window containing statistical summaries of
    TradingMetrics records that fall within that window.

    Attributes:
        timestamp: Start timestamp of the bin
        statistics: Statistical summaries for the bin
    """

    timestamp: datetime
    statistics: BinStatistics


class GranularityAggregationService:
    """Service for aggregating TradingMetrics into time bins.

    This service bins TradingMetrics records by time windows and calculates
    statistical summaries (min/max/avg/median) for each bin. This enables
    efficient data retrieval at different zoom levels without overwhelming
    the client with raw tick data.

    The service uses database aggregation functions (MIN, MAX, AVG) for
    efficiency and calculates median in Python using statistics.median.
    Example:
        >>> service = GranularityAggregationService()
        >>> bins = service.aggregate_metrics(
        ...     execution=execution,
        ...     granularity_seconds=300  # 5-minute bins
        ... )
        >>> for bin in bins:
        ...     print(f"Bin at {bin.timestamp}: avg PnL = {bin.statistics.realized_pnl_avg}")
    """

    def aggregate_metrics(
        self,
        execution: "Executions",
        granularity_seconds: int,
    ) -> list[AggregatedBin]:
        """Aggregate TradingMetrics into time bins.

        Groups TradingMetrics records by time windows and calculates
        statistical summaries for each bin. Bins are non-overlapping
        time windows of size granularity_seconds.

        The algorithm:
        1. Query all TradingMetrics for the execution, ordered by timestamp
        2. Group metrics into bins based on floor(timestamp / granularity)
        3. For each bin, calculate min/max/avg/median for all metrics
        4. Return list of AggregatedBin objects

        Args:
            execution: The execution to aggregate metrics for
            granularity_seconds: Bin size in seconds (must be > 0)

        Returns:
            List of AggregatedBin with statistical summaries, ordered by timestamp

        Raises:
            ValueError: If granularity_seconds <= 0
            ValueError: If execution has no TradingMetrics records"""
        from apps.trading.models.metrics import TradingMetrics

        # Validate granularity
        if granularity_seconds <= 0:
            raise ValueError("granularity_seconds must be positive")

        # Query all metrics for this execution
        metrics_qs = TradingMetrics.objects.filter(execution=execution).order_by("timestamp")

        if not metrics_qs.exists():
            # Use pk instead of id for type safety
            exec_pk = execution.pk if execution.pk is not None else "unknown"
            raise ValueError(f"No TradingMetrics found for execution {exec_pk}")

        # Convert queryset to list for binning
        all_metrics = list(metrics_qs)

        # Group metrics into bins
        bins_dict: dict[datetime, list] = {}

        for metric in all_metrics:
            # Calculate bin timestamp (floor to granularity)
            bin_timestamp = self._calculate_bin_timestamp(metric.timestamp, granularity_seconds)

            # Add metric to appropriate bin
            if bin_timestamp not in bins_dict:
                bins_dict[bin_timestamp] = []
            bins_dict[bin_timestamp].append(metric)

        # Calculate statistics for each bin
        aggregated_bins: list[AggregatedBin] = []

        for bin_timestamp in sorted(bins_dict.keys()):
            bin_metrics = bins_dict[bin_timestamp]
            statistics = self.calculate_bin_statistics(bin_metrics)

            aggregated_bins.append(
                AggregatedBin(
                    timestamp=bin_timestamp,
                    statistics=statistics,
                )
            )

        return aggregated_bins

    def calculate_bin_statistics(
        self,
        metrics: list,
    ) -> BinStatistics:
        """Calculate min/max/avg/median for a bin of metrics.

        Uses database aggregation functions where possible for efficiency,
        and calculates median in Python using statistics.median.

        Args:
            metrics: List of TradingMetrics in the bin (must not be empty)

        Returns:
            BinStatistics with all statistical summaries

        Raises:
            ValueError: If metrics list is empty"""
        if not metrics:
            raise ValueError("metrics list cannot be empty")

        # Extract values for each field
        realized_pnl_values = [m.realized_pnl for m in metrics]
        unrealized_pnl_values = [m.unrealized_pnl for m in metrics]
        tick_ask_min_values = [m.tick_ask_min for m in metrics]
        tick_ask_max_values = [m.tick_ask_max for m in metrics]
        tick_ask_avg_values = [m.tick_ask_avg for m in metrics]
        tick_bid_min_values = [m.tick_bid_min for m in metrics]
        tick_bid_max_values = [m.tick_bid_max for m in metrics]
        tick_bid_avg_values = [m.tick_bid_avg for m in metrics]
        tick_mid_min_values = [m.tick_mid_min for m in metrics]
        tick_mid_max_values = [m.tick_mid_max for m in metrics]
        tick_mid_avg_values = [m.tick_mid_avg for m in metrics]

        # Calculate statistics
        return BinStatistics(
            # Realized PnL statistics
            realized_pnl_min=min(realized_pnl_values),
            realized_pnl_max=max(realized_pnl_values),
            realized_pnl_avg=self._calculate_avg(realized_pnl_values),
            realized_pnl_median=self._calculate_median(realized_pnl_values),
            # Unrealized PnL statistics
            unrealized_pnl_min=min(unrealized_pnl_values),
            unrealized_pnl_max=max(unrealized_pnl_values),
            unrealized_pnl_avg=self._calculate_avg(unrealized_pnl_values),
            unrealized_pnl_median=self._calculate_median(unrealized_pnl_values),
            # Tick ask statistics (use min of mins, max of maxs, avg of avgs)
            tick_ask_min=min(tick_ask_min_values),
            tick_ask_max=max(tick_ask_max_values),
            tick_ask_avg=self._calculate_avg(tick_ask_avg_values),
            tick_ask_median=self._calculate_median(tick_ask_avg_values),
            # Tick bid statistics
            tick_bid_min=min(tick_bid_min_values),
            tick_bid_max=max(tick_bid_max_values),
            tick_bid_avg=self._calculate_avg(tick_bid_avg_values),
            tick_bid_median=self._calculate_median(tick_bid_avg_values),
            # Tick mid statistics
            tick_mid_min=min(tick_mid_min_values),
            tick_mid_max=max(tick_mid_max_values),
            tick_mid_avg=self._calculate_avg(tick_mid_avg_values),
            tick_mid_median=self._calculate_median(tick_mid_avg_values),
            # Trade count (sum of trades, but since total_trades is cumulative,
            # we take the max value in the bin)
            trade_count=max(m.total_trades for m in metrics),
        )

    def _calculate_bin_timestamp(
        self,
        timestamp: datetime,
        granularity_seconds: int,
    ) -> datetime:
        """Calculate the bin timestamp for a given timestamp.

        Bins are aligned to granularity boundaries. For example, with
        granularity=300 (5 minutes), timestamps are floored to the nearest
        5-minute mark (00:00, 00:05, 00:10, etc.).

        Args:
            timestamp: The timestamp to bin
            granularity_seconds: Bin size in seconds

        Returns:
            Bin start timestamp (floored to granularity boundary)"""
        # Convert timestamp to Unix epoch seconds
        epoch_seconds = int(timestamp.timestamp())

        # Floor to granularity boundary
        bin_epoch = (epoch_seconds // granularity_seconds) * granularity_seconds

        # Convert back to datetime
        return datetime.fromtimestamp(bin_epoch, tz=timestamp.tzinfo)

    def _calculate_avg(self, values: list[Decimal]) -> Decimal:
        """Calculate average of Decimal values.

        Args:
            values: List of Decimal values (must not be empty)

        Returns:
            Average as Decimal"""
        if not values:
            return Decimal("0")

        total = sum(values)
        count = len(values)
        return total / Decimal(str(count))

    def _calculate_median(self, values: list[Decimal]) -> Decimal:
        """Calculate median of Decimal values.

        Uses Python's statistics.median function. For even-length lists,
        returns the average of the two middle values.

        Args:
            values: List of Decimal values (must not be empty)

        Returns:
            Median as Decimal"""
        if not values:
            return Decimal("0")

        # statistics.median works with Decimal
        return Decimal(str(statistics.median(values)))
