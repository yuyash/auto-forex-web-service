"""Unit tests for MetricsCollectionService."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.test import TestCase

from apps.trading.dataclasses.metrics import ExecutionMetrics
from apps.trading.dataclasses.state import ExecutionState
from apps.trading.dataclasses.tick import Tick
from apps.trading.dataclasses.trade import OpenPosition
from apps.trading.enums import TaskType
from apps.trading.models.execution import Executions
from apps.trading.services.metrics_collection import (
    MetricsCollectionService,
)


class DummyStrategyState:
    """Dummy strategy state for testing."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "DummyStrategyState":
        """Create from dict."""
        return DummyStrategyState()


class TestMetricsCollectionService(TestCase):
    """Test suite for MetricsCollectionService.

    Tests:
    - Snapshot creation with various tick data
    - Sequence number increment
    - Error handling for invalid data
    - Edge cases: missing fields, zero values, negative PnL
    """

    def setUp(self):
        """Set up test fixtures."""
        self.service = MetricsCollectionService()

        # Create test execution
        self.execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

    def test_create_metrics_snapshot_basic(self):
        """Test creating a basic metrics snapshot."""
        # Create test tick
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        # Create test state
        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=0,
            metrics=ExecutionMetrics(
                total_trades=5,
                total_pnl=Decimal("100.50"),
            ),
        )

        # Create snapshot
        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Verify metrics were created
        assert metrics.id is not None  # type: ignore[attr-defined]
        assert metrics.execution == self.execution
        assert metrics.sequence == 0
        assert metrics.timestamp == tick.timestamp
        assert metrics.realized_pnl == Decimal("100.50")
        assert metrics.unrealized_pnl == Decimal("0")
        assert metrics.total_pnl == Decimal("100.50")
        assert metrics.open_positions == 0
        assert metrics.total_trades == 5

    def test_create_metrics_snapshot_with_open_positions(self):
        """Test creating snapshot with open positions."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1050"),
            ask=Decimal("1.1052"),
            mid=Decimal("1.1051"),
        )

        # Create open position (long)
        position = OpenPosition(
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=10000,
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("500.00"),
            unrealized_pips=Decimal("50.0"),
            timestamp=datetime.now(UTC).isoformat(),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[position],
            ticks_processed=10,
            metrics=ExecutionMetrics(
                total_trades=2,
                total_pnl=Decimal("50.00"),
            ),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Verify unrealized PnL calculation
        # Long position: (current_bid - entry_price) * units
        # (1.1050 - 1.1000) * 10000 = 0.005 * 10000 = 50.00
        assert metrics.unrealized_pnl == Decimal("50.00")
        assert metrics.realized_pnl == Decimal("50.00")
        assert metrics.total_pnl == Decimal("100.00")
        assert metrics.open_positions == 1

    def test_sequence_number_increment(self):
        """Test that sequence numbers increment correctly."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=0,
            metrics=ExecutionMetrics(),
        )

        # Create first snapshot
        metrics1 = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )
        assert metrics1.sequence == 0

        # Create second snapshot
        metrics2 = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )
        assert metrics2.sequence == 1

        # Create third snapshot
        metrics3 = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )
        assert metrics3.sequence == 2

    def test_calculate_tick_statistics(self):
        """Test tick statistics calculation."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        stats = self.service.calculate_tick_statistics(tick)

        # For single tick, min/max/avg should all be the same
        assert stats.ask_min == Decimal("1.1002")
        assert stats.ask_max == Decimal("1.1002")
        assert stats.ask_avg == Decimal("1.1002")
        assert stats.bid_min == Decimal("1.1000")
        assert stats.bid_max == Decimal("1.1000")
        assert stats.bid_avg == Decimal("1.1000")
        assert stats.mid_min == Decimal("1.1001")
        assert stats.mid_max == Decimal("1.1001")
        assert stats.mid_avg == Decimal("1.1001")

    def test_error_handling_missing_tick_data(self):
        """Test error handling when tick_data is None."""
        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=0,
            metrics=ExecutionMetrics(),
        )

        with pytest.raises(ValueError, match="tick_data is required"):
            self.service.create_metrics_snapshot(
                execution=self.execution,
                tick_data=None,  # type: ignore
                current_state=state,
            )

    def test_error_handling_missing_current_state(self):
        """Test error handling when current_state is None."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        with pytest.raises(ValueError, match="current_state is required"):
            self.service.create_metrics_snapshot(
                execution=self.execution,
                tick_data=tick,
                current_state=None,  # type: ignore
            )

    def test_error_handling_missing_tick_fields(self):
        """Test error handling when tick is missing required fields."""

        # Create a mock object without required fields
        class InvalidTick:
            pass

        invalid_tick = InvalidTick()

        with pytest.raises(ValueError, match="must have 'ask' field"):
            self.service.calculate_tick_statistics(invalid_tick)  # type: ignore

    def test_edge_case_zero_values(self):
        """Test handling of zero values in metrics."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("0"),
            open_positions=[],
            ticks_processed=0,
            metrics=ExecutionMetrics(
                total_trades=0,
                total_pnl=Decimal("0"),
            ),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        assert metrics.realized_pnl == Decimal("0")
        assert metrics.unrealized_pnl == Decimal("0")
        assert metrics.total_pnl == Decimal("0")
        assert metrics.open_positions == 0
        assert metrics.total_trades == 0

    def test_edge_case_negative_pnl(self):
        """Test handling of negative PnL values."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.0950"),
            ask=Decimal("1.0952"),
            mid=Decimal("1.0951"),
        )

        # Create losing position (long, price went down)
        position = OpenPosition(
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=10000,
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.0950"),
            unrealized_pnl=Decimal("-500.00"),
            unrealized_pips=Decimal("-50.0"),
            timestamp=datetime.now(UTC).isoformat(),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("9500"),
            open_positions=[position],
            ticks_processed=20,
            metrics=ExecutionMetrics(
                total_trades=3,
                total_pnl=Decimal("-50.00"),
            ),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Unrealized PnL: (1.0950 - 1.1000) * 10000 = -0.005 * 10000 = -50.00
        assert metrics.unrealized_pnl == Decimal("-50.00")
        assert metrics.realized_pnl == Decimal("-50.00")
        assert metrics.total_pnl == Decimal("-100.00")

    def test_edge_case_short_position(self):
        """Test unrealized PnL calculation for short positions."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.0950"),
            ask=Decimal("1.0952"),
            mid=Decimal("1.0951"),
        )

        # Create short position (price went down, profit)
        position = OpenPosition(
            position_id="1",
            instrument="EUR_USD",
            direction="short",
            units=10000,
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.0952"),
            unrealized_pnl=Decimal("480.00"),
            unrealized_pips=Decimal("48.0"),
            timestamp=datetime.now(UTC).isoformat(),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[position],
            ticks_processed=15,
            metrics=ExecutionMetrics(
                total_trades=1,
                total_pnl=Decimal("0"),
            ),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Short position: (entry_price - current_ask) * units
        # (1.1000 - 1.0952) * 10000 = 0.0048 * 10000 = 48.00
        assert metrics.unrealized_pnl == Decimal("48.00")

    def test_tick_statistics_stored_correctly(self):
        """Test that tick statistics are stored correctly in database."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=0,
            metrics=ExecutionMetrics(),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Verify tick statistics in database
        assert metrics.tick_ask_min == Decimal("1.1002")
        assert metrics.tick_ask_max == Decimal("1.1002")
        assert metrics.tick_ask_avg == Decimal("1.1002")
        assert metrics.tick_bid_min == Decimal("1.1000")
        assert metrics.tick_bid_max == Decimal("1.1000")
        assert metrics.tick_bid_avg == Decimal("1.1000")
        assert metrics.tick_mid_min == Decimal("1.1001")
        assert metrics.tick_mid_max == Decimal("1.1001")
        assert metrics.tick_mid_avg == Decimal("1.1001")

    def test_multiple_open_positions(self):
        """Test unrealized PnL with multiple open positions."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(UTC),
            bid=Decimal("1.1050"),
            ask=Decimal("1.1052"),
            mid=Decimal("1.1051"),
        )

        # Create multiple positions
        position1 = OpenPosition(
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=10000,
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("500.00"),
            unrealized_pips=Decimal("50.0"),
            timestamp=datetime.now(UTC).isoformat(),
        )
        position2 = OpenPosition(
            position_id="2",
            instrument="EUR_USD",
            direction="long",
            units=5000,
            entry_price=Decimal("1.1020"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("150.00"),
            unrealized_pips=Decimal("30.0"),
            timestamp=datetime.now(UTC).isoformat(),
        )

        state = ExecutionState(
            strategy_state=DummyStrategyState(),
            current_balance=Decimal("10000"),
            open_positions=[position1, position2],
            ticks_processed=25,
            metrics=ExecutionMetrics(
                total_trades=2,
                total_pnl=Decimal("0"),
            ),
        )

        metrics = self.service.create_metrics_snapshot(
            execution=self.execution,
            tick_data=tick,
            current_state=state,
        )

        # Position 1: (1.1050 - 1.1000) * 10000 = 0.005 * 10000 = 50.00
        # Position 2: (1.1050 - 1.1020) * 5000 = 0.003 * 5000 = 15.00
        # Total: 65.00
        assert metrics.unrealized_pnl == Decimal("65.00")
        assert metrics.open_positions == 2
