"""Unit tests for ExecutionState model."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.trading.models.state import ExecutionState


@pytest.mark.django_db
class TestExecutionState:
    """Test suite for ExecutionState model."""

    def test_create_execution_state(self):
        """Test creating an ExecutionState model instance."""
        task_id = uuid.uuid4()
        celery_task_id = "test-celery-task-123"

        state = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id=celery_task_id,
            strategy_state={"layer_count": 1, "positions": []},
            current_balance=Decimal("10000.00"),
            ticks_processed=100,
            last_tick_timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

        assert state.id is not None
        assert state.task_type == "backtest"
        assert state.task_id == task_id
        assert state.celery_task_id == celery_task_id
        assert state.strategy_state == {"layer_count": 1, "positions": []}
        assert state.current_balance == Decimal("10000.00")
        assert state.ticks_processed == 100
        assert state.last_tick_timestamp == datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        assert state.created_at is not None
        assert state.updated_at is not None

    def test_unique_constraint(self):
        """Test that the unique constraint on task_type, task_id, celery_task_id works."""
        task_id = uuid.uuid4()
        celery_task_id = "test-celery-task-123"

        # Create first state
        ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id=celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000.00"),
            ticks_processed=0,
        )

        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            ExecutionState.objects.create(
                task_type="backtest",
                task_id=task_id,
                celery_task_id=celery_task_id,
                strategy_state={},
                current_balance=Decimal("10000.00"),
                ticks_processed=0,
            )

    def test_update_execution_state(self):
        """Test updating an ExecutionState model."""
        task_id = uuid.uuid4()

        # Create initial state
        state = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="test-update-123",
            strategy_state={"layer_count": 1},
            current_balance=Decimal("10000.00"),
            ticks_processed=100,
        )

        # Update state
        state.strategy_state = {"layer_count": 2, "updated": True}
        state.current_balance = Decimal("10500.00")
        state.ticks_processed = 200
        state.last_tick_timestamp = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        state.save()

        # Verify updates persisted
        state.refresh_from_db()
        assert state.strategy_state == {"layer_count": 2, "updated": True}
        assert state.current_balance == Decimal("10500.00")
        assert state.ticks_processed == 200
        assert state.last_tick_timestamp == datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

    def test_str_representation(self):
        """Test string representation of ExecutionState model."""
        task_id = uuid.uuid4()

        state = ExecutionState.objects.create(
            task_type="trading",
            task_id=task_id,
            celery_task_id="test-str-123",
            strategy_state={},
            current_balance=Decimal("10000.00"),
            ticks_processed=150,
        )

        expected = f"ExecutionState(trading:{task_id}, ticks=150)"
        assert str(state) == expected

    def test_default_values(self):
        """Test default values for optional fields."""
        task_id = uuid.uuid4()

        state = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="test-defaults-123",
            current_balance=Decimal("10000.00"),
        )

        assert state.strategy_state == {}
        assert state.ticks_processed == 0
        assert state.last_tick_timestamp is None

    def test_query_by_task(self):
        """Test querying ExecutionState by task_type and task_id."""
        task_id_1 = uuid.uuid4()
        task_id_2 = uuid.uuid4()

        # Create states for different tasks
        ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id_1,
            celery_task_id="celery-1",
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id_2,
            celery_task_id="celery-2",
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        ExecutionState.objects.create(
            task_type="trading",
            task_id=task_id_1,
            celery_task_id="celery-3",
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        # Query by task_type and task_id
        backtest_states = ExecutionState.objects.filter(
            task_type="backtest",
            task_id=task_id_1,
        )
        assert backtest_states.count() == 1
        assert backtest_states.first().celery_task_id == "celery-1"

        trading_states = ExecutionState.objects.filter(
            task_type="trading",
            task_id=task_id_1,
        )
        assert trading_states.count() == 1
        assert trading_states.first().celery_task_id == "celery-3"

    def test_query_by_celery_task_id(self):
        """Test querying ExecutionState by celery_task_id."""
        task_id = uuid.uuid4()
        celery_task_id = "unique-celery-123"

        ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id=celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        # Query by celery_task_id
        states = ExecutionState.objects.filter(celery_task_id=celery_task_id)
        assert states.count() == 1
        assert states.first().task_id == task_id

    def test_multiple_celery_tasks_same_task(self):
        """Test that multiple celery tasks can exist for the same task (different executions)."""
        task_id = uuid.uuid4()

        # Create first execution
        state1 = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="celery-execution-1",
            strategy_state={"execution": 1},
            current_balance=Decimal("10000.00"),
            ticks_processed=100,
        )

        # Create second execution (restart)
        state2 = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="celery-execution-2",
            strategy_state={"execution": 2},
            current_balance=Decimal("10000.00"),
            ticks_processed=0,
        )

        # Both should exist
        assert state1.id != state2.id
        assert state1.celery_task_id != state2.celery_task_id

        # Query all states for this task
        states = ExecutionState.objects.filter(task_type="backtest", task_id=task_id)
        assert states.count() == 2

    def test_strategy_state_json_field(self):
        """Test that strategy_state can store complex JSON structures."""
        task_id = uuid.uuid4()

        complex_state = {
            "layer_count": 3,
            "layers": [
                {"id": 1, "positions": [{"units": 1000, "price": "150.25"}]},
                {"id": 2, "positions": [{"units": 2000, "price": "150.50"}]},
            ],
            "settings": {
                "max_layers": 5,
                "retracement_threshold": 0.5,
            },
            "metadata": {
                "created": "2025-01-15T10:00:00Z",
                "version": "1.0",
            },
        }

        state = ExecutionState.objects.create(
            task_type="trading",
            task_id=task_id,
            celery_task_id="test-json-123",
            strategy_state=complex_state,
            current_balance=Decimal("10000.00"),
        )

        # Verify complex structure persisted
        state.refresh_from_db()
        assert state.strategy_state == complex_state
        assert state.strategy_state["layer_count"] == 3
        assert len(state.strategy_state["layers"]) == 2
        assert state.strategy_state["settings"]["max_layers"] == 5

    def test_balance_precision(self):
        """Test that current_balance maintains decimal precision."""
        task_id = uuid.uuid4()

        state = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="test-precision-123",
            strategy_state={},
            current_balance=Decimal("10123.4567890123"),
        )

        state.refresh_from_db()
        assert state.current_balance == Decimal("10123.4567890123")

    def test_ordering(self):
        """Test that ExecutionState inherits ordering from UUIDModel."""
        task_id = uuid.uuid4()

        # Create states at different times
        state1 = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="celery-1",
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        state2 = ExecutionState.objects.create(
            task_type="backtest",
            task_id=task_id,
            celery_task_id="celery-2",
            strategy_state={},
            current_balance=Decimal("10000.00"),
        )

        # Query should return newest first (from UUIDModel ordering)
        states = ExecutionState.objects.filter(task_type="backtest", task_id=task_id)
        assert states[0].id == state2.id
        assert states[1].id == state1.id
