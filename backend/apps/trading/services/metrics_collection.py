"""Metrics collection service for creating TradingMetrics snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.dataclasses.state import ExecutionState
    from apps.trading.dataclasses.tick import Tick
    from apps.trading.models.execution import Executions
    from apps.trading.models.metrics import TradingMetrics


@dataclass(frozen=True, slots=True)
class TickStatistics:
    """Statistical summary of tick prices.

    Contains min/max/avg statistics for ask, bid, and mid prices.
    All values are Decimal for precision.

    Attributes:
        ask_min: Minimum ask price
        ask_max: Maximum ask price
        ask_avg: Average ask price
        bid_min: Minimum bid price
        bid_max: Maximum bid price
        bid_avg: Average bid price
        mid_min: Minimum mid price
        mid_max: Maximum mid price
        mid_avg: Average mid price
    """

    ask_min: Decimal
    ask_max: Decimal
    ask_avg: Decimal
    bid_min: Decimal
    bid_max: Decimal
    bid_avg: Decimal
    mid_min: Decimal
    mid_max: Decimal
    mid_avg: Decimal


class MetricsCollectionService:
    """Service for creating TradingMetrics snapshots during execution.

    This service is responsible for:
    - Creating TradingMetrics records on every tick
    - Calculating tick statistics (min/max/avg for ask/bid/mid)
    - Auto-incrementing sequence numbers
    - Extracting PnL and position data from execution state

    Requirements: 1.2, 3.4

    Example:
        >>> service = MetricsCollectionService()
        >>> metrics = service.create_metrics_snapshot(
        ...     execution=execution,
        ...     tick_data=tick,
        ...     current_state=state
        ... )
    """

    def create_metrics_snapshot(
        self,
        execution: "Executions",
        tick_data: "Tick",
        current_state: "ExecutionState",
    ) -> "TradingMetrics":
        """Create a new TradingMetrics snapshot for the current tick.

        This method:
        1. Calculates tick statistics from tick_data
        2. Extracts PnL and position metrics from current_state
        3. Auto-increments the sequence number
        4. Creates and saves a TradingMetrics record

        Args:
            execution: The execution instance
            tick_data: Current tick with ask/bid/mid prices
            current_state: Current execution state (positions, PnL, etc.)

        Returns:
            Created TradingMetrics instance

        Raises:
            ValueError: If tick_data is missing required fields
            ValueError: If current_state is missing required fields

        Requirements: 1.2, 3.4
        """
        from apps.trading.models.metrics import TradingMetrics

        # Validate inputs
        if not tick_data:
            raise ValueError("tick_data is required")
        if not current_state:
            raise ValueError("current_state is required")

        # Calculate tick statistics
        tick_stats = self.calculate_tick_statistics(tick_data)

        # Get next sequence number
        sequence = self._get_next_sequence(execution)

        # Extract metrics from current state
        metrics = current_state.metrics
        realized_pnl = getattr(metrics, "total_pnl", Decimal("0"))

        # Calculate unrealized PnL from open positions
        unrealized_pnl = self._calculate_unrealized_pnl(current_state.open_positions, tick_data)

        total_pnl = realized_pnl + unrealized_pnl

        # Create TradingMetrics record
        trading_metrics = TradingMetrics.objects.create(
            execution=execution,
            sequence=sequence,
            timestamp=tick_data.timestamp,
            # PnL metrics
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            # Position metrics
            open_positions=len(current_state.open_positions),
            total_trades=metrics.total_trades,
            # Tick statistics - Ask
            tick_ask_min=tick_stats.ask_min,
            tick_ask_max=tick_stats.ask_max,
            tick_ask_avg=tick_stats.ask_avg,
            # Tick statistics - Bid
            tick_bid_min=tick_stats.bid_min,
            tick_bid_max=tick_stats.bid_max,
            tick_bid_avg=tick_stats.bid_avg,
            # Tick statistics - Mid
            tick_mid_min=tick_stats.mid_min,
            tick_mid_max=tick_stats.mid_max,
            tick_mid_avg=tick_stats.mid_avg,
        )

        return trading_metrics

    def calculate_tick_statistics(self, tick_data: "Tick") -> TickStatistics:
        """Calculate min/max/avg statistics for ask/bid/mid prices.

        For a single tick, min/max/avg are all the same value since we only
        have one data point. This method is designed to be extensible for
        future enhancements where multiple ticks might be aggregated.

        Args:
            tick_data: Current tick data with ask/bid/mid prices

        Returns:
            TickStatistics with min/max/avg for ask/bid/mid

        Raises:
            ValueError: If tick_data is missing required price fields

        Requirements: 3.4
        """
        # Validate tick data has required fields
        if not hasattr(tick_data, "ask") or tick_data.ask is None:
            raise ValueError("tick_data must have 'ask' field")
        if not hasattr(tick_data, "bid") or tick_data.bid is None:
            raise ValueError("tick_data must have 'bid' field")
        if not hasattr(tick_data, "mid") or tick_data.mid is None:
            raise ValueError("tick_data must have 'mid' field")

        # For a single tick, min/max/avg are all the same
        return TickStatistics(
            ask_min=tick_data.ask,
            ask_max=tick_data.ask,
            ask_avg=tick_data.ask,
            bid_min=tick_data.bid,
            bid_max=tick_data.bid,
            bid_avg=tick_data.bid,
            mid_min=tick_data.mid,
            mid_max=tick_data.mid,
            mid_avg=tick_data.mid,
        )

    def _get_next_sequence(self, execution: "Executions") -> int:
        """Get the next sequence number for TradingMetrics.

        Queries the database for the highest sequence number for this
        execution and returns the next value. Starts at 0 if no records exist.

        Args:
            execution: The execution instance

        Returns:
            Next monotonic sequence number (0-indexed)

        Requirements: 1.2
        """
        from django.db.models import Max

        from apps.trading.models.metrics import TradingMetrics

        result = TradingMetrics.objects.filter(execution=execution).aggregate(
            max_seq=Max("sequence")
        )
        max_sequence = result["max_seq"]
        return (max_sequence + 1) if max_sequence is not None else 0

    def _calculate_unrealized_pnl(
        self,
        open_positions: list,
        tick_data: "Tick",
    ) -> Decimal:
        """Calculate unrealized PnL from open positions.

        For each open position, calculates the PnL based on the current
        market price (from tick_data) versus the entry price.

        Args:
            open_positions: List of open position objects
            tick_data: Current tick with market prices

        Returns:
            Total unrealized PnL across all open positions

        Requirements: 1.2
        """
        if not open_positions:
            return Decimal("0")

        total_unrealized = Decimal("0")

        for position in open_positions:
            # Get position details
            units = getattr(position, "units", 0)
            entry_price = getattr(position, "entry_price", Decimal("0"))
            direction = getattr(position, "direction", "").lower()

            if units == 0 or entry_price == 0:
                continue

            # Determine current price based on position direction
            # For long positions, use bid (exit price)
            # For short positions, use ask (exit price)
            if direction == "long":
                current_price = tick_data.bid
                pnl = (current_price - entry_price) * Decimal(str(abs(units)))
            elif direction == "short":
                current_price = tick_data.ask
                pnl = (entry_price - current_price) * Decimal(str(abs(units)))
            else:
                # Unknown direction, skip
                continue

            total_unrealized += pnl

        return total_unrealized
