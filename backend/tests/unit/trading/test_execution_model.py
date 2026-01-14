"""Unit tests for TaskExecution model helper methods."""

from decimal import Decimal

import pytest

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models.execution import TaskExecution


@pytest.mark.django_db
class TestTaskExecutionStateManagement:
    """Test state management methods on TaskExecution model.

    Requirements: 4.1, 4.2, 4.3
    """

    def test_save_state_snapshot_creates_snapshot(self):
        """Test that save_state_snapshot creates a new snapshot with correct data."""
        # Create execution
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Save state snapshot
        strategy_state = {"layer_count": 2, "locked": False}
        balance = Decimal("10500.50")
        positions = [{"instrument": "USD_JPY", "units": 1000}]
        ticks = 1500
        timestamp = "2025-01-12T10:30:00Z"
        metrics = {"total_pnl": "500.50"}

        snapshot = execution.save_state_snapshot(
            strategy_state=strategy_state,
            current_balance=balance,
            open_positions=positions,
            ticks_processed=ticks,
            last_tick_timestamp=timestamp,
            metrics=metrics,
        )

        # Verify snapshot was created
        assert snapshot is not None
        assert snapshot.execution == execution
        assert snapshot.sequence == 0
        assert snapshot.strategy_state == strategy_state
        assert snapshot.current_balance == balance
        assert snapshot.open_positions == positions
        assert snapshot.ticks_processed == ticks
        assert snapshot.last_tick_timestamp == timestamp
        assert snapshot.metrics == metrics

    def test_save_state_snapshot_increments_sequence(self):
        """Test that multiple snapshots get sequential sequence numbers."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Save first snapshot
        snapshot1 = execution.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=100,
        )

        # Save second snapshot
        snapshot2 = execution.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10100"),
            open_positions=[],
            ticks_processed=200,
        )

        # Save third snapshot
        snapshot3 = execution.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10200"),
            open_positions=[],
            ticks_processed=300,
        )

        # Verify sequences are monotonically increasing
        assert snapshot1.sequence == 0
        assert snapshot2.sequence == 1
        assert snapshot3.sequence == 2

    def test_load_latest_state_returns_most_recent(self):
        """Test that load_latest_state returns the most recent snapshot."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Save multiple snapshots
        execution.save_state_snapshot(
            strategy_state={"step": 1},
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=100,
        )

        execution.save_state_snapshot(
            strategy_state={"step": 2},
            current_balance=Decimal("10100"),
            open_positions=[],
            ticks_processed=200,
        )

        execution.save_state_snapshot(
            strategy_state={"step": 3},
            current_balance=Decimal("10200"),
            open_positions=[{"instrument": "EUR_USD"}],
            ticks_processed=300,
            last_tick_timestamp="2025-01-12T10:30:00Z",
            metrics={"pnl": "200"},
        )

        # Load latest state
        state = execution.load_latest_state()

        # Verify it's the most recent
        assert state is not None
        assert state["strategy_state"] == {"step": 3}
        assert state["current_balance"] == Decimal("10200")
        assert state["open_positions"] == [{"instrument": "EUR_USD"}]
        assert state["ticks_processed"] == 300
        assert state["last_tick_timestamp"] == "2025-01-12T10:30:00Z"
        assert state["metrics"] == {"pnl": "200"}
        assert state["sequence"] == 2

    def test_load_latest_state_returns_none_when_no_snapshots(self):
        """Test that load_latest_state returns None when no snapshots exist."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        state = execution.load_latest_state()
        assert state is None

    def test_next_snapshot_sequence_starts_at_zero(self):
        """Test that _next_snapshot_sequence returns 0 for first snapshot."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        sequence = execution._next_snapshot_sequence()
        assert sequence == 0

    def test_save_state_snapshot_handles_defaults(self):
        """Test that save_state_snapshot handles None/empty defaults correctly."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Save with minimal parameters
        snapshot = execution.save_state_snapshot(
            strategy_state={},  # type: ignore[arg-type]
            current_balance=Decimal("10000"),
            open_positions=[],  # type: ignore[arg-type]
            ticks_processed=0,
        )

        # Verify defaults
        assert snapshot.strategy_state == {}
        assert snapshot.open_positions == []
        assert snapshot.last_tick_timestamp == ""
        assert snapshot.metrics == {}


@pytest.mark.django_db
class TestTaskExecutionEventEmission:
    """Test event emission methods on TaskExecution model.

    Requirements: 1.6
    """

    def test_emit_event_creates_event(self):
        """Test that emit_event creates a new event with correct data."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Emit event
        event_data = {
            "tick": {
                "instrument": "USD_JPY",
                "bid": "157.234",
                "ask": "157.236",
            }
        }

        event = execution.emit_event(
            event_type="tick_received",
            event_data=event_data,
            strategy_type="floor",
            timestamp="2025-01-12T10:30:00Z",
        )

        # Verify event was created
        assert event is not None
        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "tick_received"
        assert event.strategy_type == "floor"
        assert event.event == event_data
        assert event.timestamp is not None

    def test_emit_event_increments_sequence(self):
        """Test that multiple events get sequential sequence numbers."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Emit multiple events
        event1 = execution.emit_event(
            event_type="tick_received",
            event_data={"tick": 1},
        )

        event2 = execution.emit_event(
            event_type="strategy_signal",
            event_data={"signal": "buy"},
        )

        event3 = execution.emit_event(
            event_type="trade_executed",
            event_data={"trade": "long"},
        )

        # Verify sequences are monotonically increasing
        assert event1.sequence == 0
        assert event2.sequence == 1
        assert event3.sequence == 2

    def test_emit_event_handles_missing_timestamp(self):
        """Test that emit_event works without timestamp."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        event = execution.emit_event(
            event_type="status_changed",
            event_data={"status": "running"},
        )

        # Verify event was created without timestamp
        assert event is not None
        assert event.timestamp is None

    def test_emit_event_handles_empty_strategy_type(self):
        """Test that emit_event works with empty strategy_type."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        event = execution.emit_event(
            event_type="error_occurred",
            event_data={"error": "test error"},
        )

        # Verify event was created with empty strategy_type
        assert event is not None
        assert event.strategy_type == ""

    def test_next_event_sequence_starts_at_zero(self):
        """Test that _next_event_sequence returns 0 for first event."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        sequence = execution._next_event_sequence()
        assert sequence == 0

    def test_emit_event_handles_none_event_data(self):
        """Test that emit_event handles None event_data correctly."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        event = execution.emit_event(
            event_type="test_event",
            event_data={},  # type: ignore[arg-type]
        )

        # Verify event was created with empty dict
        assert event is not None
        assert event.event == {}


@pytest.mark.django_db
class TestTaskExecutionIntegration:
    """Integration tests for state and event methods working together."""

    def test_state_and_events_use_independent_sequences(self):
        """Test that state snapshots and events maintain independent sequences."""
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Interleave state snapshots and events
        event1 = execution.emit_event("event1", {"data": 1})
        snapshot1 = execution.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=100,
        )
        event2 = execution.emit_event("event2", {"data": 2})
        snapshot2 = execution.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10100"),
            open_positions=[],
            ticks_processed=200,
        )
        event3 = execution.emit_event("event3", {"data": 3})

        # Verify independent sequences
        assert event1.sequence == 0
        assert event2.sequence == 1
        assert event3.sequence == 2

        assert snapshot1.sequence == 0
        assert snapshot2.sequence == 1

    def test_multiple_executions_have_independent_sequences(self):
        """Test that different executions maintain independent sequences."""
        execution1 = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        execution2 = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=2,
            status=TaskStatus.RUNNING,
        )

        # Create events for both executions
        event1_1 = execution1.emit_event("event", {"exec": 1})
        event2_1 = execution2.emit_event("event", {"exec": 2})
        event1_2 = execution1.emit_event("event", {"exec": 1})
        event2_2 = execution2.emit_event("event", {"exec": 2})

        # Verify independent sequences
        assert event1_1.sequence == 0
        assert event1_2.sequence == 1
        assert event2_1.sequence == 0
        assert event2_2.sequence == 1

        # Create snapshots for both executions
        snapshot1_1 = execution1.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=100,
        )
        snapshot2_1 = execution2.save_state_snapshot(
            strategy_state={},
            current_balance=Decimal("10000"),
            open_positions=[],
            ticks_processed=100,
        )

        # Verify independent sequences
        assert snapshot1_1.sequence == 0
        assert snapshot2_1.sequence == 0
