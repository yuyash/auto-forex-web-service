"""
Unit tests for StateSynchronizer service.

Tests the StateSynchronizer state transition management including:
- All state transition paths (running, stopped, completed, failed)
- Notification broadcasting for each transition
- Cleanup operations on stop/fail
- State consistency verification

Requirements: 3.1, 3.2, 3.4
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus, TaskType
from trading.execution_models import TaskExecution
from trading.services.state_synchronizer import StateSynchronizer

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create a test strategy configuration."""
    from trading.models import StrategyConfig

    return StrategyConfig.objects.create(
        user=user,
        name="Test Config",
        strategy_type="floor",
        parameters={"floor_level": 150.0, "units": 1000},
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create a test backtest task."""
    return BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        start_time=timezone.now(),
        end_time=timezone.now(),
        instrument="USD_JPY",
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def task_execution(db, backtest_task):
    """Create a test task execution."""
    return TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=backtest_task.id,
        execution_number=1,
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def state_synchronizer():
    """Create a StateSynchronizer instance."""
    return StateSynchronizer(task_type="backtest")


@pytest.mark.django_db
class TestTransitionToRunning:
    """Test transition to running state."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_running_success(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test successful transition to running state."""
        # Transition to running
        state_synchronizer.transition_to_running(backtest_task, task_execution)

        # Verify task status updated
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.RUNNING

        # Verify execution status updated
        task_execution.refresh_from_db()
        assert task_execution.status == TaskStatus.RUNNING
        assert task_execution.started_at is not None
        assert task_execution.progress == 0

        # Verify notification was sent
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        assert call_args["user_id"] == backtest_task.user.id
        assert call_args["task_id"] == backtest_task.id
        assert call_args["task_name"] == backtest_task.name
        assert call_args["task_type"] == "backtest"
        assert call_args["status"] == TaskStatus.RUNNING
        assert call_args["execution_id"] == task_execution.id

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_running_sets_timestamp(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that transition sets started_at timestamp."""
        # Record time before transition
        before_time = timezone.now()

        # Transition to running
        state_synchronizer.transition_to_running(backtest_task, task_execution)

        # Verify timestamp was set
        task_execution.refresh_from_db()
        assert task_execution.started_at is not None
        assert task_execution.started_at >= before_time

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_running_resets_progress(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that transition resets progress to 0."""
        # Set initial progress
        task_execution.progress = 50
        task_execution.save()

        # Transition to running
        state_synchronizer.transition_to_running(backtest_task, task_execution)

        # Verify progress reset to 0
        task_execution.refresh_from_db()
        assert task_execution.progress == 0


@pytest.mark.django_db
class TestTransitionToStopped:
    """Test transition to stopped state."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_stopped_success(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test successful transition to stopped state."""
        # Set initial state to running
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_at = timezone.now()
        task_execution.save()

        # Transition to stopped
        state_synchronizer.transition_to_stopped(backtest_task, task_execution)

        # Verify task status updated
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.STOPPED

        # Verify execution status updated
        task_execution.refresh_from_db()
        assert task_execution.status == TaskStatus.STOPPED
        assert task_execution.completed_at is not None

        # Verify notification was sent
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        assert call_args["status"] == TaskStatus.STOPPED

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_stopped_sets_completed_timestamp(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that transition sets completed_at timestamp."""
        # Set initial state to running
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_at = timezone.now()
        task_execution.save()

        # Record time before transition
        before_time = timezone.now()

        # Transition to stopped
        state_synchronizer.transition_to_stopped(backtest_task, task_execution)

        # Verify timestamp was set
        task_execution.refresh_from_db()
        assert task_execution.completed_at is not None
        assert task_execution.completed_at >= before_time


@pytest.mark.django_db
class TestTransitionToCompleted:
    """Test transition to completed state."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_completed_success(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test successful transition to completed state."""
        # Set initial state to running
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_at = timezone.now()
        task_execution.progress = 75
        task_execution.save()

        # Transition to completed
        state_synchronizer.transition_to_completed(backtest_task, task_execution)

        # Verify task status updated
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.COMPLETED

        # Verify execution status updated
        task_execution.refresh_from_db()
        assert task_execution.status == TaskStatus.COMPLETED
        assert task_execution.completed_at is not None
        assert task_execution.progress == 100

        # Verify notification was sent
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        assert call_args["status"] == TaskStatus.COMPLETED

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_completed_sets_progress_to_100(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that transition sets progress to 100%."""
        # Set initial state with partial progress
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.progress = 85
        task_execution.save()

        # Transition to completed
        state_synchronizer.transition_to_completed(backtest_task, task_execution)

        # Verify progress set to 100
        task_execution.refresh_from_db()
        assert task_execution.progress == 100


@pytest.mark.django_db
class TestTransitionToFailed:
    """Test transition to failed state."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_failed_success(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test successful transition to failed state."""
        # Set initial state to running
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.started_at = timezone.now()
        task_execution.save()

        # Transition to failed with error message
        error_message = "Test error: Database connection failed"
        state_synchronizer.transition_to_failed(backtest_task, task_execution, error_message)

        # Verify task status updated
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.FAILED

        # Verify execution status updated
        task_execution.refresh_from_db()
        assert task_execution.status == TaskStatus.FAILED
        assert task_execution.completed_at is not None
        assert task_execution.error_message == error_message

        # Verify notification was sent with error message
        mock_notification.assert_called_once()
        call_args = mock_notification.call_args[1]
        assert call_args["status"] == TaskStatus.FAILED
        assert call_args["error_message"] == error_message

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_to_failed_stores_error_message(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that error message is stored in execution."""
        # Set initial state to running
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.save()

        # Transition to failed
        error_message = "Critical error occurred"
        state_synchronizer.transition_to_failed(backtest_task, task_execution, error_message)

        # Verify error message stored
        task_execution.refresh_from_db()
        assert task_execution.error_message == error_message


@pytest.mark.django_db
class TestVerifyStateConsistency:
    """Test state consistency verification."""

    def test_verify_consistency_no_executions(self, state_synchronizer, backtest_task):
        """Test consistency check when task has no executions."""
        # Task should be in CREATED state with no executions
        is_consistent, message = state_synchronizer.verify_state_consistency(backtest_task.id)

        assert is_consistent is True
        assert "no executions" in message.lower()
        assert "CREATED" in message

    def test_verify_consistency_matching_states(
        self, state_synchronizer, backtest_task, task_execution
    ):
        """Test consistency check when states match."""
        # Set both to RUNNING
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.save()

        # Verify consistency
        is_consistent, message = state_synchronizer.verify_state_consistency(backtest_task.id)

        assert is_consistent is True
        assert "consistent" in message.lower()
        assert TaskStatus.RUNNING in message

    def test_verify_consistency_mismatched_states(
        self, state_synchronizer, backtest_task, task_execution
    ):
        """Test consistency check when states don't match."""
        # Set task to COMPLETED but execution to RUNNING
        backtest_task.status = TaskStatus.COMPLETED
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.save()

        # Verify inconsistency detected
        is_consistent, message = state_synchronizer.verify_state_consistency(backtest_task.id)

        assert is_consistent is False
        assert "mismatch" in message.lower()
        assert TaskStatus.COMPLETED in message
        assert TaskStatus.RUNNING in message

    def test_verify_consistency_task_not_found(self, state_synchronizer):
        """Test consistency check for non-existent task."""
        # Check non-existent task
        is_consistent, message = state_synchronizer.verify_state_consistency(99999)

        assert is_consistent is False
        assert "not found" in message.lower()

    def test_verify_consistency_created_with_execution(
        self, state_synchronizer, backtest_task, task_execution
    ):
        """Test inconsistency when task is CREATED but has executions."""
        # Task is CREATED but has an execution
        backtest_task.status = TaskStatus.CREATED
        backtest_task.save()
        task_execution.status = TaskStatus.COMPLETED
        task_execution.save()

        # Should detect inconsistency
        is_consistent, message = state_synchronizer.verify_state_consistency(backtest_task.id)

        assert is_consistent is False
        assert "mismatch" in message.lower()


@pytest.mark.django_db
class TestTransactionAtomicity:
    """Test that state transitions are atomic."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_transition_rollback_on_notification_failure(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that database changes rollback if notification fails."""
        # Make notification raise an exception
        mock_notification.side_effect = Exception("Notification service unavailable")

        # Set initial state
        backtest_task.status = TaskStatus.CREATED
        backtest_task.save()
        task_execution.status = TaskStatus.CREATED
        task_execution.save()

        # Attempt transition (should raise exception)
        with pytest.raises(Exception, match="Simulated error"):
            state_synchronizer.transition_to_running(backtest_task, task_execution)

        # Verify states were rolled back
        backtest_task.refresh_from_db()
        task_execution.refresh_from_db()
        assert backtest_task.status == TaskStatus.CREATED
        assert task_execution.status == TaskStatus.CREATED


@pytest.mark.django_db
class TestMultipleExecutions:
    """Test state synchronization with multiple executions."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_verify_consistency_uses_latest_execution(
        self, mock_notification, state_synchronizer, backtest_task
    ):
        """Test that consistency check uses the latest execution."""
        # Create multiple executions
        TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            execution_number=1,
            status=TaskStatus.COMPLETED,
        )

        TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            execution_number=2,
            status=TaskStatus.RUNNING,
        )

        # Set task status to match latest execution
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        # Verify consistency (should check against execution2)
        is_consistent, message = state_synchronizer.verify_state_consistency(backtest_task.id)

        assert is_consistent is True
        assert TaskStatus.RUNNING in message


@pytest.mark.django_db
class TestNotificationBroadcasting:
    """Test notification broadcasting for each transition."""

    @patch("trading.services.state_synchronizer.send_task_status_notification")
    def test_all_transitions_broadcast_notifications(
        self, mock_notification, state_synchronizer, backtest_task, task_execution
    ):
        """Test that all state transitions broadcast notifications."""
        # Test running transition
        state_synchronizer.transition_to_running(backtest_task, task_execution)
        assert mock_notification.call_count == 1

        # Test stopped transition
        state_synchronizer.transition_to_stopped(backtest_task, task_execution)
        assert mock_notification.call_count == 2

        # Reset for completed transition
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.save()

        # Test completed transition
        state_synchronizer.transition_to_completed(backtest_task, task_execution)
        assert mock_notification.call_count == 3

        # Reset for failed transition
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()
        task_execution.status = TaskStatus.RUNNING
        task_execution.save()

        # Test failed transition
        state_synchronizer.transition_to_failed(backtest_task, task_execution, "Test error")
        assert mock_notification.call_count == 4
