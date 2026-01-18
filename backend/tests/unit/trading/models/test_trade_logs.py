"""Unit tests for TradeLogs model."""

import pytest
from django.db import IntegrityError

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, TradeLogs


@pytest.mark.django_db
class TestTradeLogsModel:
    """Test suite for TradeLogs model."""

    @pytest.fixture
    def execution(self):
        """Create a test execution."""
        return Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

    def test_create_trade_log_with_valid_data(self, execution):
        """Test creating TradeLogs with valid fields."""
        trade_data = {
            "instrument": "EUR_USD",
            "units": 1000,
            "price": 1.1234,
            "type": "MARKET",
        }

        trade_log = TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade=trade_data,
        )

        assert trade_log.id is not None
        assert trade_log.execution == execution
        assert trade_log.sequence == 0
        assert trade_log.trade == trade_data
        assert trade_log.created_at is not None

    def test_unique_constraint_on_execution_sequence(self, execution):
        """Test that (execution, sequence) must be unique."""
        # Create first trade log
        TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={"type": "MARKET"},
        )

        # Attempt to create duplicate with same execution and sequence
        with pytest.raises(IntegrityError):
            TradeLogs.objects.create(
                execution=execution,
                sequence=0,  # Same sequence
                trade={"type": "LIMIT"},
            )

    def test_related_name_access_from_execution(self, execution):
        """Test accessing TradeLogs from Execution via related_name."""
        # Create multiple trade logs
        TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={"type": "MARKET"},
        )
        TradeLogs.objects.create(
            execution=execution,
            sequence=1,
            trade={"type": "LIMIT"},
        )

        # Access via related_name
        trade_logs = list(execution.trade_logs.all())
        assert len(trade_logs) == 2
        assert trade_logs[0].sequence == 0
        assert trade_logs[1].sequence == 1

    def test_cascade_delete_on_execution_delete(self, execution):
        """Test that trade logs are deleted when execution is deleted."""
        TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={"type": "MARKET"},
        )

        assert TradeLogs.objects.filter(execution=execution).count() == 1

        # Delete execution
        execution.delete()

        # Trade logs should be deleted
        assert TradeLogs.objects.count() == 0
