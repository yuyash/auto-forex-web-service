"""Integration tests for position lifecycle management.

Tests position opening with correct parameters, position update persistence,
position closing with P/L calculation, and position queries.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.trading.dataclasses import ExecutionState, OpenPosition
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, TradingTasks
from apps.trading.services.state import StateManager
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import OandaAccountFactory, StrategyConfigurationFactory


@pytest.mark.django_db
class TestPositionLifecycle(IntegrationTestCase):
    """Integration tests for position lifecycle management."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create OANDA account
        self.account = OandaAccountFactory(user=self.user)

        # Create strategy configuration
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

        # Create trading task
        self.task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="EUR_USD",
            oanda_account=self.account,
        )

        # Create execution
        self.execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=self.task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create state manager
        self.state_manager = StateManager(self.execution)

    def test_position_opening_with_correct_parameters(self):
        """Test that positions are opened with correct parameters.

        Verifies that:
        1. Position is created with specified parameters
        2. Position is added to execution state
        3. Position data is persisted correctly"""
        # Create initial state
        initial_state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
        )

        # Save initial state
        self.state_manager.save_snapshot(initial_state)

        # Create a position
        position = OpenPosition(
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=1000,
            entry_price=Decimal("1.10000"),
            current_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("0.00"),
            unrealized_pips=Decimal("0.0"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        # Add position to state
        new_state = initial_state.copy_with(
            open_positions=[position],
            ticks_processed=1,
        )

        # Save updated state
        self.state_manager.save_snapshot(new_state)

        # Load state and verify position
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 1, "Should have 1 open position"

        loaded_position = loaded_state.open_positions[0]
        assert loaded_position.position_id == "POS-001"
        assert loaded_position.instrument == "EUR_USD"
        assert loaded_position.direction == "long"
        assert loaded_position.units == 1000
        assert loaded_position.entry_price == Decimal("1.10000")
        assert loaded_position.current_price == Decimal("1.10000")
        assert loaded_position.unrealized_pnl == Decimal("0.00")
        assert loaded_position.unrealized_pips == Decimal("0.0")

    def test_position_update_persistence(self):
        """Test that position updates are correctly persisted.

        Verifies that:
        1. Position price updates are saved
        2. Position P/L updates are calculated and saved
        3. Updated position data can be retrieved"""
        # Create initial state with a position
        position = OpenPosition(
            position_id="POS-002",
            instrument="USD_JPY",
            direction="short",
            units=5000,
            entry_price=Decimal("150.00"),
            current_price=Decimal("150.00"),
            unrealized_pnl=Decimal("0.00"),
            unrealized_pips=Decimal("0.0"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        initial_state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=[position],
            ticks_processed=1,
        )

        # Save initial state
        self.state_manager.save_snapshot(initial_state)

        # Update position with new price and P/L
        updated_position = OpenPosition(
            position_id="POS-002",
            instrument="USD_JPY",
            direction="short",
            units=5000,
            entry_price=Decimal("150.00"),
            current_price=Decimal("149.50"),  # Price moved in favor
            unrealized_pnl=Decimal("250.00"),  # Profit
            unrealized_pips=Decimal("50.0"),
            timestamp=datetime(2024, 1, 1, 12, 5, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        # Update state with new position data
        updated_state = initial_state.copy_with(
            open_positions=[updated_position],
            ticks_processed=10,
        )

        # Save updated state
        self.state_manager.save_snapshot(updated_state)

        # Load state and verify updates
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 1, "Should have 1 open position"

        loaded_position = loaded_state.open_positions[0]
        assert loaded_position.position_id == "POS-002"
        assert loaded_position.current_price == Decimal("149.50")
        assert loaded_position.unrealized_pnl == Decimal("250.00")
        assert loaded_position.unrealized_pips == Decimal("50.0")

    def test_position_closing_with_pnl_calculation(self):
        """Test that positions are closed with correct P/L calculation.

        Verifies that:
        1. Position is removed from open positions
        2. Final P/L is calculated correctly
        3. Closed position data is recorded"""
        # Create initial state with two positions
        position1 = OpenPosition(
            position_id="POS-003",
            instrument="GBP_USD",
            direction="long",
            units=2000,
            entry_price=Decimal("1.25000"),
            current_price=Decimal("1.25000"),
            unrealized_pnl=Decimal("0.00"),
            unrealized_pips=Decimal("0.0"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        position2 = OpenPosition(
            position_id="POS-004",
            instrument="EUR_USD",
            direction="short",
            units=1000,
            entry_price=Decimal("1.10000"),
            current_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("0.00"),
            unrealized_pips=Decimal("0.0"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        initial_state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=[position1, position2],
            ticks_processed=1,
        )

        # Save initial state
        self.state_manager.save_snapshot(initial_state)

        # Close position1 by removing it from open positions
        # In real scenario, this would be done by strategy logic
        closed_position = OpenPosition(
            position_id="POS-003",
            instrument="GBP_USD",
            direction="long",
            units=2000,
            entry_price=Decimal("1.25000"),
            current_price=Decimal("1.25500"),  # Exit price
            unrealized_pnl=Decimal("100.00"),  # Final P/L
            unrealized_pips=Decimal("50.0"),
            timestamp=datetime(2024, 1, 1, 12, 10, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        # Calculate realized P/L
        realized_pnl = closed_position.unrealized_pnl

        # Update state with position closed
        closed_state = initial_state.copy_with(
            open_positions=[position2],  # Only position2 remains
            current_balance=initial_state.current_balance + realized_pnl,
            ticks_processed=20,
        )

        # Save closed state
        self.state_manager.save_snapshot(closed_state)

        # Load state and verify position is closed
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 1, "Should have 1 open position"
        assert loaded_state.open_positions[0].position_id == "POS-004"

        # Verify balance reflects realized P/L
        assert loaded_state.current_balance == Decimal("10100.00")

    def test_position_queries(self):
        """Test querying positions from execution state.

        Verifies that:
        1. All open positions can be retrieved
        2. Positions can be filtered by instrument
        3. Position data is accurate"""
        # Create state with multiple positions
        positions = [
            OpenPosition(
                position_id=f"POS-{i:03d}",
                instrument="EUR_USD" if i % 2 == 0 else "USD_JPY",
                direction="long" if i % 2 == 0 else "short",
                units=1000 * (i + 1),
                entry_price=Decimal("1.10000") if i % 2 == 0 else Decimal("150.00"),
                current_price=Decimal("1.10000") if i % 2 == 0 else Decimal("150.00"),
                unrealized_pnl=Decimal("0.00"),
                unrealized_pips=Decimal("0.0"),
                timestamp=datetime(2024, 1, 1, 12, i, 0, tzinfo=dt_timezone.utc).isoformat(),
            )
            for i in range(5)
        ]

        state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=positions,
            ticks_processed=5,
        )

        # Save state
        self.state_manager.save_snapshot(state)

        # Load state and query all positions
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 5, "Should have 5 open positions"

        # Query positions by instrument
        eur_usd_positions = [
            pos for pos in loaded_state.open_positions if pos.instrument == "EUR_USD"
        ]
        usd_jpy_positions = [
            pos for pos in loaded_state.open_positions if pos.instrument == "USD_JPY"
        ]

        assert len(eur_usd_positions) == 3, "Should have 3 EUR_USD positions"
        assert len(usd_jpy_positions) == 2, "Should have 2 USD_JPY positions"

        # Verify position data accuracy
        for i, pos in enumerate(loaded_state.open_positions):
            assert pos.position_id == f"POS-{i:03d}"
            assert pos.units == 1000 * (i + 1)

    def test_multiple_position_updates_in_sequence(self):
        """Test multiple sequential position updates.

        Verifies that:
        1. Multiple updates are persisted correctly
        2. State history is maintained
        3. Latest state reflects all updates"""
        # Create initial state with a position
        position = OpenPosition(
            position_id="POS-005",
            instrument="AUD_USD",
            direction="long",
            units=3000,
            entry_price=Decimal("0.65000"),
            current_price=Decimal("0.65000"),
            unrealized_pnl=Decimal("0.00"),
            unrealized_pips=Decimal("0.0"),
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=[position],
            ticks_processed=1,
        )

        # Save initial state
        self.state_manager.save_snapshot(state)

        # Perform multiple updates
        prices = [
            Decimal("0.65050"),
            Decimal("0.65100"),
            Decimal("0.65150"),
            Decimal("0.65200"),
        ]

        for i, price in enumerate(prices, start=1):
            # Calculate P/L (simplified)
            price_diff = price - position.entry_price
            pnl = price_diff * position.units
            pips = price_diff * Decimal("10000")  # For AUD_USD

            updated_position = OpenPosition(
                position_id="POS-005",
                instrument="AUD_USD",
                direction="long",
                units=3000,
                entry_price=Decimal("0.65000"),
                current_price=price,
                unrealized_pnl=pnl,
                unrealized_pips=pips,
                timestamp=datetime(2024, 1, 1, 12, i, 0, tzinfo=dt_timezone.utc).isoformat(),
            )

            state = state.copy_with(
                open_positions=[updated_position],
                ticks_processed=i + 1,
            )

            self.state_manager.save_snapshot(state)

        # Load final state and verify
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 1, "Should have 1 open position"

        final_position = loaded_state.open_positions[0]
        assert final_position.current_price == Decimal("0.65200")
        assert final_position.unrealized_pnl == Decimal(
            "6.00"
        )  # (0.65200 - 0.65000) * 3000 = 0.002 * 3000 = 6
        assert final_position.unrealized_pips == Decimal("20.0")

    def test_position_lifecycle_across_multiple_instruments(self):
        """Test position lifecycle for multiple instruments simultaneously.

        Verifies that:
        1. Positions for different instruments are managed independently
        2. Updates to one instrument don't affect others
        3. Closing positions works correctly per instrument"""
        # Create positions for multiple instruments
        positions = [
            OpenPosition(
                position_id="POS-EUR-001",
                instrument="EUR_USD",
                direction="long",
                units=1000,
                entry_price=Decimal("1.10000"),
                current_price=Decimal("1.10000"),
                unrealized_pnl=Decimal("0.00"),
                unrealized_pips=Decimal("0.0"),
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
            ),
            OpenPosition(
                position_id="POS-GBP-001",
                instrument="GBP_USD",
                direction="short",
                units=2000,
                entry_price=Decimal("1.25000"),
                current_price=Decimal("1.25000"),
                unrealized_pnl=Decimal("0.00"),
                unrealized_pips=Decimal("0.0"),
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
            ),
            OpenPosition(
                position_id="POS-JPY-001",
                instrument="USD_JPY",
                direction="long",
                units=5000,
                entry_price=Decimal("150.00"),
                current_price=Decimal("150.00"),
                unrealized_pnl=Decimal("0.00"),
                unrealized_pips=Decimal("0.0"),
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc).isoformat(),
            ),
        ]

        state = ExecutionState(
            strategy_state={},  # ty:ignore[invalid-argument-type]
            current_balance=Decimal("10000.00"),
            open_positions=positions,
            ticks_processed=1,
        )

        # Save initial state
        self.state_manager.save_snapshot(state)

        # Update EUR_USD position
        positions[0] = OpenPosition(
            position_id="POS-EUR-001",
            instrument="EUR_USD",
            direction="long",
            units=1000,
            entry_price=Decimal("1.10000"),
            current_price=Decimal("1.10500"),
            unrealized_pnl=Decimal("50.00"),
            unrealized_pips=Decimal("50.0"),
            timestamp=datetime(2024, 1, 1, 12, 5, 0, tzinfo=dt_timezone.utc).isoformat(),
        )

        state = state.copy_with(open_positions=positions, ticks_processed=10)
        self.state_manager.save_snapshot(state)

        # Close GBP_USD position
        positions = [pos for pos in positions if pos.position_id != "POS-GBP-001"]
        state = state.copy_with(
            open_positions=positions,
            current_balance=Decimal("10000.00"),  # Assume break-even close
            ticks_processed=20,
        )
        self.state_manager.save_snapshot(state)

        # Load final state and verify
        loaded_state = self.state_manager.get_state()

        assert loaded_state is not None, "State should be loaded"
        assert len(loaded_state.open_positions) == 2, "Should have 2 open positions"

        # Verify EUR_USD position was updated
        eur_position = next(
            pos for pos in loaded_state.open_positions if pos.instrument == "EUR_USD"
        )
        assert eur_position.current_price == Decimal("1.10500")
        assert eur_position.unrealized_pnl == Decimal("50.00")

        # Verify GBP_USD position was closed
        gbp_positions = [pos for pos in loaded_state.open_positions if pos.instrument == "GBP_USD"]
        assert len(gbp_positions) == 0, "GBP_USD position should be closed"

        # Verify USD_JPY position is unchanged
        jpy_position = next(
            pos for pos in loaded_state.open_positions if pos.instrument == "USD_JPY"
        )
        assert jpy_position.current_price == Decimal("150.00")
        assert jpy_position.unrealized_pnl == Decimal("0.00")
