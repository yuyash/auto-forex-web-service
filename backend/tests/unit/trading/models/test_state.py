"""Unit tests for trading state models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.enums import TaskType
from apps.trading.models import Executions, ExecutionStateSnapshot

User = get_user_model()


@pytest.mark.django_db
class TestExecutionStateSnapshotModel:
    """Test ExecutionStateSnapshot model."""

    def test_create_execution_state_snapshot(self):
        """Test creating execution state snapshot."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

        from decimal import Decimal

        snapshot = ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=1,
            strategy_state={"positions": []},
            current_balance=Decimal("10000.00"),
            open_positions=[],
        )

        assert snapshot.execution == execution
        assert snapshot.sequence == 1
        assert snapshot.current_balance == Decimal("10000.00")

    def test_multiple_snapshots_for_execution(self):
        """Test multiple snapshots can be created for an execution."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

        from decimal import Decimal

        snapshot1 = ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=1,
            strategy_state={},
            current_balance=Decimal("10000.00"),
            open_positions=[],
        )

        snapshot2 = ExecutionStateSnapshot.objects.create(
            execution=execution,
            sequence=2,
            strategy_state={},
            current_balance=Decimal("10100.00"),
            open_positions=[],
        )

        assert execution.state_snapshots.count() == 2
        assert snapshot1.sequence < snapshot2.sequence
