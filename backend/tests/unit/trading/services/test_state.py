"""Unit tests for StateManager service.

Tests the StateManager class which handles loading, saving, and validating
execution state for task resumability.
"""

from decimal import Decimal

import pytest

from apps.trading.dataclasses import ExecutionState
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import ExecutionStateSnapshot, TaskExecution
from apps.trading.services.state import StateManager


@pytest.mark.django_db
class TestStateManager:
    """Test suite for StateManager class."""

    @pytest.fixture
    def execution(self):
        """Create a TaskExecution for testing."""
        return TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

    @pytest.fixture
    def state_manager(self, execution):
        """Create a StateManager instance for testing."""
        return StateManager(execution)

    def test_initialization(self, execution):
        """Test StateManager initialization."""
        manager = StateManager(execution)
        assert manager.execution == execution

    def test_load_or_initialize_with_no_snapshots(self, state_manager):
        """Test load_or_initialize returns new state when no snapshots exist."""
        initial_balance = Decimal("10000.00")
        initial_strategy_state = {"test": "value"}

        state = state_manager.load_or_initialize(
            initial_balance=initial_balance,
            initial_strategy_state=initial_strategy_state,
        )

        assert isinstance(state, ExecutionState)
        assert state.strategy_state == {"test": "value"}
        assert state.current_balance == initial_balance
        assert state.open_positions == []
        assert state.ticks_processed == 0
        assert state.last_tick_timestamp is None
        assert state.metrics == {}

    def test_load_or_initialize_with_default_strategy_state(self, state_manager):
        """Test load_or_initialize uses empty dict when strategy state not provided."""
        initial_balance = Decimal("10000.00")

        state = state_manager.load_or_initialize(initial_balance=initial_balance)

        assert state.strategy_state == {}

    def test_load_or_initialize_loads_existing_snapshot(self, state_manager, execution):
        """Test load_or_initialize loads most recent snapshot when it exists."""
        # Create a snapshot
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=0,
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[{"id": "123"}],
            ticks_processed=100,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={"pnl": 500},
        )

        state = state_manager.load_or_initialize(initial_balance=Decimal("10000.00"))

        assert state.strategy_state == {"layer": 1}
        assert state.current_balance == Decimal("10500.00")
        assert state.open_positions == [{"id": "123"}]
        assert state.ticks_processed == 100
        assert state.last_tick_timestamp == "2025-01-09T10:00:00Z"
        assert state.metrics == {"pnl": 500}

    def test_load_or_initialize_loads_most_recent_snapshot(self, state_manager, execution):
        """Test load_or_initialize loads the most recent snapshot when multiple exist."""
        # Create multiple snapshots
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=0,
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[],
            ticks_processed=100,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={},
        )
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=1,
            strategy_state={"layer": 2},
            current_balance=Decimal("11000.00"),
            open_positions=[{"id": "456"}],
            ticks_processed=200,
            last_tick_timestamp="2025-01-09T11:00:00Z",
            metrics={"pnl": 1000},
        )

        state = state_manager.load_or_initialize(initial_balance=Decimal("10000.00"))

        # Should load the most recent (sequence=1)
        assert state.strategy_state == {"layer": 2}
        assert state.current_balance == Decimal("11000.00")
        assert state.ticks_processed == 200

    def test_update_strategy_state(self, state_manager):
        """Test update_strategy_state creates new state with updated strategy state."""
        original_state = ExecutionState(
            strategy_state={"old": "value"},
            current_balance=Decimal("10000.00"),
            open_positions=[{"id": "123"}],
            ticks_processed=50,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={"pnl": 100},
        )

        new_strategy_state = {"new": "value", "layer": 1}
        updated_state = state_manager.update_strategy_state(original_state, new_strategy_state)

        # Strategy state should be updated
        assert updated_state.strategy_state == {"new": "value", "layer": 1}

        # All other fields should be preserved
        assert updated_state.current_balance == Decimal("10000.00")
        assert updated_state.open_positions == [{"id": "123"}]
        assert updated_state.ticks_processed == 50
        assert updated_state.last_tick_timestamp == "2025-01-09T10:00:00Z"
        assert updated_state.metrics == {"pnl": 100}

        # Original state should be unchanged (immutable pattern)
        assert original_state.strategy_state == {"old": "value"}

    def test_save_snapshot_creates_snapshot(self, state_manager, execution):
        """Test save_snapshot creates a new snapshot record."""
        state = ExecutionState(
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[{"id": "123"}],
            ticks_processed=100,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={"pnl": 500},
        )

        snapshot = state_manager.save_snapshot(state)

        assert isinstance(snapshot, ExecutionStateSnapshot)
        assert snapshot.execution == execution
        assert snapshot.sequence == 0
        assert snapshot.strategy_state == {"layer": 1}
        assert snapshot.current_balance == Decimal("10500.00")
        assert snapshot.open_positions == [{"id": "123"}]
        assert snapshot.ticks_processed == 100
        assert snapshot.last_tick_timestamp == "2025-01-09T10:00:00Z"
        assert snapshot.metrics == {"pnl": 500}

    def test_save_snapshot_increments_sequence(self, state_manager, execution):
        """Test save_snapshot uses monotonically increasing sequence numbers."""
        state1 = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )
        state2 = ExecutionState(
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[],
            ticks_processed=100,
            last_tick_timestamp=None,
            metrics={},
        )

        snapshot1 = state_manager.save_snapshot(state1)
        snapshot2 = state_manager.save_snapshot(state2)

        assert snapshot1.sequence == 0
        assert snapshot2.sequence == 1

    def test_save_snapshot_handles_none_timestamp(self, state_manager):
        """Test save_snapshot converts None timestamp to empty string."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )

        snapshot = state_manager.save_snapshot(state)

        assert snapshot.last_tick_timestamp == ""

    def test_get_state_returns_none_when_no_snapshots(self, state_manager):
        """Test get_state returns None when no snapshots exist."""
        state = state_manager.get_state()
        assert state is None

    def test_get_state_returns_most_recent_snapshot(self, state_manager, execution):
        """Test get_state returns the most recent snapshot."""
        # Create multiple snapshots
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=0,
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[],
            ticks_processed=100,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={},
        )
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=1,
            strategy_state={"layer": 2},
            current_balance=Decimal("11000.00"),
            open_positions=[{"id": "456"}],
            ticks_processed=200,
            last_tick_timestamp="2025-01-09T11:00:00Z",
            metrics={"pnl": 1000},
        )

        state = state_manager.get_state()

        assert state is not None
        assert state.strategy_state == {"layer": 2}
        assert state.current_balance == Decimal("11000.00")
        assert state.ticks_processed == 200

    def test_get_state_converts_empty_timestamp_to_none(self, state_manager, execution):
        """Test get_state converts empty string timestamp to None."""
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=0,
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp="",
            metrics={},
        )

        state = state_manager.get_state()

        assert state is not None
        assert state.last_tick_timestamp is None

    def test_validate_state_accepts_valid_state(self, state_manager):
        """Test validate_state returns True for valid state."""
        state = ExecutionState(
            strategy_state={"layer": 1},
            current_balance=Decimal("10000.00"),
            open_positions=[{"id": "123"}],
            ticks_processed=100,
            last_tick_timestamp="2025-01-09T10:00:00Z",
            metrics={"pnl": 500},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is True
        assert error is None

    def test_validate_state_rejects_non_dict_strategy_state(self, state_manager):
        """Test validate_state rejects non-dictionary strategy state."""
        state = ExecutionState(
            strategy_state="not a dict",  # type: ignore
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "strategy_state must be a dictionary"

    def test_validate_state_rejects_negative_balance(self, state_manager):
        """Test validate_state rejects negative balance."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("-100.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "current_balance cannot be negative"

    def test_validate_state_rejects_non_list_positions(self, state_manager):
        """Test validate_state rejects non-list open positions."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions="not a list",  # type: ignore
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "open_positions must be a list"

    def test_validate_state_rejects_negative_ticks(self, state_manager):
        """Test validate_state rejects negative ticks processed."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=-10,
            last_tick_timestamp=None,
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "ticks_processed cannot be negative"

    def test_validate_state_rejects_non_string_timestamp(self, state_manager):
        """Test validate_state rejects non-string timestamp."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=12345,  # type: ignore
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "last_tick_timestamp must be a string or None"

    def test_validate_state_rejects_non_dict_metrics(self, state_manager):
        """Test validate_state rejects non-dictionary metrics."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics="not a dict",  # type: ignore
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is False
        assert error == "metrics must be a dictionary"

    def test_validate_state_accepts_none_timestamp(self, state_manager):
        """Test validate_state accepts None as valid timestamp."""
        state = ExecutionState(
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
        )

        is_valid, error = state_manager.validate_state(state)

        assert is_valid is True
        assert error is None

    def test_clear_state_deletes_all_snapshots(self, state_manager, execution):
        """Test clear_state deletes all snapshots for the execution."""
        # Create multiple snapshots
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=0,
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp="",
            metrics={},
        )
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=1,
            strategy_state={"layer": 1},
            current_balance=Decimal("10500.00"),
            open_positions=[],
            ticks_processed=100,
            last_tick_timestamp="",
            metrics={},
        )

        # Verify snapshots exist
        assert ExecutionStateSnapshot.objects.filter(execution=execution).count() == 2

        # Clear state
        state_manager.clear_state()

        # Verify all snapshots are deleted
        assert ExecutionStateSnapshot.objects.filter(execution=execution).count() == 0

    def test_next_snapshot_sequence_starts_at_zero(self, state_manager):
        """Test _next_snapshot_sequence returns 0 when no snapshots exist."""
        sequence = state_manager._next_snapshot_sequence()
        assert sequence == 0

    def test_next_snapshot_sequence_increments(self, state_manager, execution):
        """Test _next_snapshot_sequence increments from last snapshot."""
        ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=5,
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp="",
            metrics={},
        )

        sequence = state_manager._next_snapshot_sequence()
        assert sequence == 6
