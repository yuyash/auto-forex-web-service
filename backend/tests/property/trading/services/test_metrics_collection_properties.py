"""Property-based tests for MetricsCollectionService.

Feature: trading-app-refactor

This module contains property-based tests that verify universal properties
of the MetricsCollectionService across all possible inputs.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apps.trading.dataclasses.metrics import ExecutionMetrics
from apps.trading.dataclasses.state import ExecutionState
from apps.trading.dataclasses.tick import Tick
from apps.trading.dataclasses.trade import OpenPosition
from apps.trading.enums import TaskType
from apps.trading.models.execution import Executions
from apps.trading.models.metrics import TradingMetrics
from apps.trading.services.metrics_collection import MetricsCollectionService


class DummyStrategyState:
    """Dummy strategy state for testing."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DummyStrategyState":
        """Create from dict."""
        return DummyStrategyState()


# Hypothesis strategies for generating test data


@st.composite
def decimal_strategy(draw, min_value=-10000, max_value=10000):
    """Generate a Decimal value."""
    value = draw(
        st.floats(min_value=min_value, max_value=max_value, allow_nan=False, allow_infinity=False)
    )
    return Decimal(str(round(value, 5)))


@st.composite
def tick_strategy(draw):
    """Generate a valid Tick."""
    bid = draw(decimal_strategy(min_value=0.5, max_value=2.0))
    spread = draw(decimal_strategy(min_value=0.0001, max_value=0.01))
    ask = bid + spread
    mid = (bid + ask) / Decimal("2")

    return Tick(
        instrument="EUR_USD",
        timestamp=datetime.now(UTC),
        bid=bid,
        ask=ask,
        mid=mid,
    )


@st.composite
def open_position_strategy(draw):
    """Generate a valid OpenPosition."""
    direction = draw(st.sampled_from(["long", "short"]))
    units = draw(st.integers(min_value=1000, max_value=100000))
    entry_price = draw(decimal_strategy(min_value=0.5, max_value=2.0))
    current_price = draw(decimal_strategy(min_value=0.5, max_value=2.0))

    # Calculate unrealized PnL based on direction
    if direction == "long":
        unrealized_pnl = (current_price - entry_price) * Decimal(str(units))
    else:
        unrealized_pnl = (entry_price - current_price) * Decimal(str(units))

    return OpenPosition(
        position_id=str(draw(st.integers(min_value=1, max_value=10000))),
        instrument="EUR_USD",
        direction=direction,
        units=units,
        entry_price=entry_price,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        unrealized_pips=unrealized_pnl / Decimal("10"),  # Simplified pip calculation
        timestamp=datetime.now(UTC).isoformat(),
    )


@st.composite
def execution_state_strategy(draw):
    """Generate a valid ExecutionState."""
    num_positions = draw(st.integers(min_value=0, max_value=5))
    positions = [draw(open_position_strategy()) for _ in range(num_positions)]

    total_trades = draw(st.integers(min_value=0, max_value=100))
    total_pnl = draw(decimal_strategy())

    return ExecutionState(
        strategy_state=DummyStrategyState(),
        current_balance=draw(decimal_strategy(min_value=1000, max_value=100000)),
        open_positions=positions,
        ticks_processed=draw(st.integers(min_value=0, max_value=10000)),
        metrics=ExecutionMetrics(
            total_trades=total_trades,
            total_pnl=total_pnl,
        ),
    )


# Property 1: Tick Processing Creates Metrics
# Feature: trading-app-refactor, Property 1: Tick Processing Creates Metrics
#
# For any execution and tick data, when the execution processes the tick,
# a new TradingMetrics record should be created with a unique sequence number.
#
# Validates: Requirements 1.2


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    tick=tick_strategy(),
    state=execution_state_strategy(),
)
def test_property_1_tick_processing_creates_metrics(
    tick: Tick,
    state: ExecutionState,
    django_db_setup,
    db,
):
    """
    Feature: trading-app-refactor, Property 1: Tick Processing Creates Metrics

    For any execution and tick data, when the execution processes the tick,
    a new TradingMetrics record should be created with a unique sequence number.

    Validates: Requirements 1.2
    """
    # Create execution
    execution = Executions.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=1,
        execution_number=1,
    )

    # Get initial count
    initial_count = TradingMetrics.objects.filter(execution=execution).count()

    # Create service and snapshot
    service = MetricsCollectionService()
    metrics = service.create_metrics_snapshot(
        execution=execution,
        tick_data=tick,
        current_state=state,
    )

    # Verify a new record was created
    final_count = TradingMetrics.objects.filter(execution=execution).count()
    assert final_count == initial_count + 1, "A new TradingMetrics record should be created"

    # Verify the record has a valid sequence number
    assert metrics.sequence >= 0, "Sequence number should be non-negative"

    # Verify the record is persisted
    assert metrics.id is not None, "TradingMetrics should be saved to database"  # type: ignore[attr-defined]

    # Verify the record is associated with the execution
    assert metrics.execution == execution, "TradingMetrics should be associated with execution"

    # Clean up
    execution.delete()


# Property 2: Tick Statistics Correctness
# Feature: trading-app-refactor, Property 2: Tick Statistics Correctness
#
# For any tick data with ask/bid prices, when a TradingMetrics snapshot is created,
# the calculated tick statistics should satisfy:
# - tick_ask_min ≤ tick_ask_avg ≤ tick_ask_max
# - tick_bid_min ≤ tick_bid_avg ≤ tick_bid_max
# - tick_mid_min ≤ tick_mid_avg ≤ tick_mid_max
#
# Validates: Requirements 3.4


@settings(max_examples=100)
@given(tick=tick_strategy())
def test_property_2_tick_statistics_correctness(tick: Tick):
    """
    Feature: trading-app-refactor, Property 2: Tick Statistics Correctness

    For any tick data with ask/bid prices, when tick statistics are calculated,
    the following invariants should hold:
    - tick_ask_min ≤ tick_ask_avg ≤ tick_ask_max
    - tick_bid_min ≤ tick_bid_avg ≤ tick_bid_max
    - tick_mid_min ≤ tick_mid_avg ≤ tick_mid_max

    Validates: Requirements 3.4
    """
    service = MetricsCollectionService()
    stats = service.calculate_tick_statistics(tick)

    # Verify ask statistics invariant
    assert stats.ask_min <= stats.ask_avg <= stats.ask_max, (
        f"Ask statistics invariant violated: "
        f"min={stats.ask_min}, avg={stats.ask_avg}, max={stats.ask_max}"
    )

    # Verify bid statistics invariant
    assert stats.bid_min <= stats.bid_avg <= stats.bid_max, (
        f"Bid statistics invariant violated: "
        f"min={stats.bid_min}, avg={stats.bid_avg}, max={stats.bid_max}"
    )

    # Verify mid statistics invariant
    assert stats.mid_min <= stats.mid_avg <= stats.mid_max, (
        f"Mid statistics invariant violated: "
        f"min={stats.mid_min}, avg={stats.mid_avg}, max={stats.mid_max}"
    )

    # For a single tick, min/max/avg should all be equal
    assert stats.ask_min == stats.ask_avg == stats.ask_max == tick.ask, (
        f"For single tick, ask min/avg/max should equal tick.ask: "
        f"min={stats.ask_min}, avg={stats.ask_avg}, max={stats.ask_max}, tick.ask={tick.ask}"
    )

    assert stats.bid_min == stats.bid_avg == stats.bid_max == tick.bid, (
        f"For single tick, bid min/avg/max should equal tick.bid: "
        f"min={stats.bid_min}, avg={stats.bid_avg}, max={stats.bid_max}, tick.bid={tick.bid}"
    )

    assert stats.mid_min == stats.mid_avg == stats.mid_max == tick.mid, (
        f"For single tick, mid min/avg/max should equal tick.mid: "
        f"min={stats.mid_min}, avg={stats.mid_avg}, max={stats.mid_max}, tick.mid={tick.mid}"
    )
