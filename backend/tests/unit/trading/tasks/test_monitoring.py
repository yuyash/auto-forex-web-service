"""Unit tests for task status reconciliation."""

from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from celery.result import AsyncResult

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTasks, TradingTasks
from apps.trading.tasks.monitoring import reconcile_task_statuses


@pytest.mark.django_db
class TestReconcileTaskStatuses:
    """Unit tests for reconcile_task_statuses periodic task."""

    def test_reconcile_backtest_task_status_mismatch(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation updates BacktestTask status when mismatch detected."""
        # Create a backtest task with RUNNING status
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock Celery AsyncResult to return SUCCESS state
        with patch.object(AsyncResult, "state", "SUCCESS"):
            result = reconcile_task_statuses()

        # Verify task status was updated to COMPLETED
        task.refresh_from_db()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

        # Verify reconciliation results
        assert result["backtest_checked"] == 1
        assert result["backtest_reconciled"] == 1
        assert result["trading_checked"] == 0
        assert result["trading_reconciled"] == 0
        assert len(result["reconciled_tasks"]) == 1
        assert result["reconciled_tasks"][0]["task_type"] == "backtest"
        assert result["reconciled_tasks"][0]["new_status"] == TaskStatus.COMPLETED

    def test_reconcile_trading_task_status_mismatch(
        self,
        user,
        strategy_config,
        oanda_account,
    ) -> None:
        """Test reconciliation updates TradingTask status when mismatch detected."""
        # Create a trading task with RUNNING status
        task = TradingTasks.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading",
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock Celery AsyncResult to return FAILURE state
        with patch.object(AsyncResult, "state", "FAILURE"):
            result = reconcile_task_statuses()

        # Verify task status was updated to FAILED
        task.refresh_from_db()
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None

        # Verify reconciliation results
        assert result["backtest_checked"] == 0
        assert result["backtest_reconciled"] == 0
        assert result["trading_checked"] == 1
        assert result["trading_reconciled"] == 1
        assert len(result["reconciled_tasks"]) == 1
        assert result["reconciled_tasks"][0]["task_type"] == "trading"
        assert result["reconciled_tasks"][0]["new_status"] == TaskStatus.FAILED

    def test_reconcile_no_mismatch(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation does nothing when status matches."""
        # Create a backtest task with RUNNING status
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock Celery AsyncResult to return STARTED state (matches RUNNING)
        with patch.object(AsyncResult, "state", "STARTED"):
            result = reconcile_task_statuses()

        # Verify task status was NOT changed
        task.refresh_from_db()
        assert task.status == TaskStatus.RUNNING

        # Verify reconciliation results
        assert result["backtest_checked"] == 1
        assert result["backtest_reconciled"] == 0
        assert len(result["reconciled_tasks"]) == 0

    def test_reconcile_multiple_tasks(
        self,
        user,
        strategy_config,
        oanda_account,
    ) -> None:
        """Test reconciliation handles multiple tasks correctly."""
        # Create multiple tasks with different statuses
        backtest1 = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Backtest 1",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        backtest2 = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Backtest 2",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        trading1 = TradingTasks.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Trading 1",
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock different Celery states for each task
        def mock_get_celery_result(self):  # type: ignore[no-untyped-def]
            mock_result = MagicMock()
            if self.id == backtest1.id:  # type: ignore[attr-defined]
                mock_result.state = "SUCCESS"
            elif self.id == backtest2.id:  # type: ignore[attr-defined]
                mock_result.state = "STARTED"  # No change
            elif self.id == trading1.id:  # type: ignore[attr-defined]
                mock_result.state = "REVOKED"
            return mock_result

        with patch.object(BacktestTasks, "get_celery_result", mock_get_celery_result):
            with patch.object(TradingTasks, "get_celery_result", mock_get_celery_result):
                result = reconcile_task_statuses()

        # Verify task statuses
        backtest1.refresh_from_db()
        assert backtest1.status == TaskStatus.COMPLETED

        backtest2.refresh_from_db()
        assert backtest2.status == TaskStatus.RUNNING  # No change

        trading1.refresh_from_db()
        assert trading1.status == TaskStatus.STOPPED

        # Verify reconciliation results
        assert result["backtest_checked"] == 2
        assert result["backtest_reconciled"] == 1
        assert result["trading_checked"] == 1
        assert result["trading_reconciled"] == 1
        assert result["total_checked"] == 3
        assert result["total_reconciled"] == 2
        assert len(result["reconciled_tasks"]) == 2

    def test_reconcile_handles_errors_gracefully(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation handles errors without crashing."""
        # Create a task with RUNNING status
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock get_celery_result to raise an exception
        with patch.object(
            BacktestTasks,
            "get_celery_result",
            side_effect=Exception("Celery connection error"),
        ):
            result = reconcile_task_statuses()

        # Verify task status was NOT changed
        task.refresh_from_db()
        assert task.status == TaskStatus.RUNNING

        # Verify error was logged
        assert result["backtest_checked"] == 1
        assert result["backtest_reconciled"] == 0
        assert len(result["errors"]) == 1
        assert "Celery connection error" in result["errors"][0]

    def test_reconcile_only_checks_running_tasks(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation only checks tasks with RUNNING status."""
        # Create tasks with different statuses
        BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Completed Task",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.COMPLETED,
            celery_task_id=str(uuid4()),
        )

        BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Pending Task",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.CREATED,
        )

        BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Running Task",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock Celery AsyncResult
        with patch.object(AsyncResult, "state", "STARTED"):
            result = reconcile_task_statuses()

        # Verify only running task was checked
        assert result["backtest_checked"] == 1
        assert result["backtest_reconciled"] == 0

    def test_reconcile_sets_completed_at_for_terminal_states(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation sets completed_at for terminal states."""
        # Create a task with RUNNING status
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
            completed_at=None,
        )

        # Mock Celery AsyncResult to return SUCCESS state
        with patch.object(AsyncResult, "state", "SUCCESS"):
            reconcile_task_statuses()

        # Verify completed_at was set
        task.refresh_from_db()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_reconcile_maps_celery_states_correctly(
        self,
        user,
        strategy_config,
    ) -> None:
        """Test reconciliation maps all Celery states correctly."""
        celery_to_task_status = {
            "PENDING": TaskStatus.CREATED,
            "STARTED": TaskStatus.RUNNING,
            "SUCCESS": TaskStatus.COMPLETED,
            "FAILURE": TaskStatus.FAILED,
            "REVOKED": TaskStatus.STOPPED,
        }

        for celery_state, expected_status in celery_to_task_status.items():
            # Create a task with RUNNING status
            task = BacktestTasks.objects.create(
                user=user,
                config=strategy_config,
                name=f"Test {celery_state}",
                start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
                end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
                status=TaskStatus.RUNNING,
                celery_task_id=str(uuid4()),
            )

            # Mock Celery AsyncResult to return the specific state
            with patch.object(AsyncResult, "state", celery_state):
                reconcile_task_statuses()

            # Verify task status was updated correctly
            task.refresh_from_db()
            assert task.status == expected_status

            # Clean up for next iteration
            task.delete()
