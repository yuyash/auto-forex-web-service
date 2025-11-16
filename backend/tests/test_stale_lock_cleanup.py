"""
Unit tests for stale lock cleanup Celery task.

Tests the cleanup_stale_locks_task periodic task including:
- Detection of stale locks
- Automatic lock release
- Task status update on cleanup
- Cleanup with no stale locks

Requirements: 7.3, 7.4, 7.5
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

import pytest

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus
from trading.execution_models import TaskExecution
from trading.models import StrategyConfig
from trading.services.task_lock_manager import TaskLockManager
from trading.tasks import cleanup_stale_locks_task

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
    return StrategyConfig.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="ma_crossover",
        parameters={
            "fast_period": 10,
            "slow_period": 20,
        },
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create a test backtest task."""
    return BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        description="Test backtest task",
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now() - timedelta(days=1),
        initial_balance=Decimal("10000.00"),
        instrument="USD_JPY",
        status=TaskStatus.RUNNING,
    )


@pytest.fixture
def task_execution(db, backtest_task):
    """Create a test task execution."""
    return TaskExecution.objects.create(
        task_type="backtest",
        task_id=backtest_task.id,
        execution_number=1,
        status=TaskStatus.RUNNING,
        started_at=timezone.now() - timedelta(minutes=10),
    )


@pytest.fixture
def lock_manager():
    """Create a TaskLockManager instance."""
    return TaskLockManager()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


class TestStaleLockDetection:
    """Test detection of stale locks."""

    def test_detect_stale_lock_with_old_heartbeat(
        self, backtest_task, task_execution, lock_manager
    ):
        """Test detection of lock with old heartbeat."""
        # Acquire lock
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        # Manually set old heartbeat (simulate stale lock)
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", backtest_task.id)
        old_time = timezone.now() - timedelta(seconds=400)  # 6+ minutes ago
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": task_execution.id},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify cleanup was successful
        assert result["success"] is True
        assert result["cleaned_count"] == 1
        assert backtest_task.id in result["failed_tasks"]

        # Verify lock was released
        lock_key = lock_manager._get_lock_key("backtest", backtest_task.id)
        lock_data = cache.get(lock_key)
        assert lock_data is None

    def test_detect_stale_lock_with_no_heartbeat(self, backtest_task, task_execution, lock_manager):
        """Test detection of lock with no heartbeat data."""
        # Acquire lock
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        # Remove heartbeat (simulate missing heartbeat)
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", backtest_task.id)
        cache.delete(heartbeat_key)

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify cleanup was successful
        assert result["success"] is True
        assert result["cleaned_count"] == 1
        assert backtest_task.id in result["failed_tasks"]

    def test_no_cleanup_for_fresh_lock(self, backtest_task, task_execution, lock_manager):
        """Test that fresh lock with recent heartbeat is not cleaned up."""
        # Acquire lock
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        # Update heartbeat to ensure it's fresh
        lock_manager.update_heartbeat(task_type="backtest", task_id=backtest_task.id)

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify no cleanup occurred
        assert result["success"] is True
        assert result["cleaned_count"] == 0
        assert len(result["failed_tasks"]) == 0

        # Verify lock still exists
        lock_key = lock_manager._get_lock_key("backtest", backtest_task.id)
        lock_data = cache.get(lock_key)
        assert lock_data is not None


class TestAutomaticLockRelease:
    """Test automatic lock release."""

    def test_lock_released_on_cleanup(self, backtest_task, task_execution, lock_manager):
        """Test that stale lock is automatically released."""
        # Acquire lock
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        # Make lock stale
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", backtest_task.id)
        old_time = timezone.now() - timedelta(seconds=400)
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": task_execution.id},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            cleanup_stale_locks_task()

        # Verify lock was released
        lock_key = lock_manager._get_lock_key("backtest", backtest_task.id)
        assert cache.get(lock_key) is None

        # Verify heartbeat was removed
        assert cache.get(heartbeat_key) is None

        # Verify cancellation flag was removed
        cancel_key = lock_manager._get_cancellation_key("backtest", backtest_task.id)
        assert cache.get(cancel_key) is None

    def test_multiple_stale_locks_released(self, user, strategy_config, lock_manager):
        """Test that multiple stale locks are released."""
        # Create multiple running tasks with stale locks
        tasks = []
        for i in range(3):
            task = BacktestTask.objects.create(
                user=user,
                config=strategy_config,
                name=f"Test Backtest {i}",
                start_time=timezone.now() - timedelta(days=7),
                end_time=timezone.now() - timedelta(days=1),
                initial_balance=Decimal("10000.00"),
                instrument="USD_JPY",
                status=TaskStatus.RUNNING,
            )
            tasks.append(task)

            # Create execution
            execution = TaskExecution.objects.create(
                task_type="backtest",
                task_id=task.id,
                execution_number=1,
                status=TaskStatus.RUNNING,
                started_at=timezone.now() - timedelta(minutes=10),
            )

            # Acquire lock and make it stale
            lock_manager.acquire_lock(
                task_type="backtest",
                task_id=task.id,
                execution_id=execution.id,
            )

            heartbeat_key = lock_manager._get_heartbeat_key("backtest", task.id)
            old_time = timezone.now() - timedelta(seconds=400)
            cache.set(
                heartbeat_key,
                {"last_beat": old_time.isoformat(), "execution_id": execution.id},
                timeout=lock_manager.LOCK_TIMEOUT,
            )

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify all locks were cleaned up
        assert result["success"] is True
        assert result["cleaned_count"] == 3
        assert len(result["failed_tasks"]) == 3

        # Verify all locks were released
        for task in tasks:
            lock_key = lock_manager._get_lock_key("backtest", task.id)
            assert cache.get(lock_key) is None


class TestTaskStatusUpdate:
    """Test task status update on cleanup."""

    def test_task_status_updated_to_failed(self, backtest_task, task_execution, lock_manager):
        """Test that task status is updated to failed on cleanup."""
        # Acquire lock and make it stale
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        heartbeat_key = lock_manager._get_heartbeat_key("backtest", backtest_task.id)
        old_time = timezone.now() - timedelta(seconds=400)
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": task_execution.id},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            cleanup_stale_locks_task()

        # Verify task status was updated
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.FAILED

        # Verify execution status was updated
        task_execution.refresh_from_db()
        assert task_execution.status == TaskStatus.FAILED
        assert "stale lock" in task_execution.error_message.lower()
        assert task_execution.completed_at is not None

    def test_websocket_notification_sent(self, backtest_task, task_execution, lock_manager):
        """Test that WebSocket notification is sent on cleanup."""
        # Acquire lock and make it stale
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        heartbeat_key = lock_manager._get_heartbeat_key("backtest", backtest_task.id)
        old_time = timezone.now() - timedelta(seconds=400)
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": task_execution.id},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Run cleanup task with mocked notification
        with patch("trading.services.notifications.send_task_status_notification") as mock_notify:
            cleanup_stale_locks_task()

            # Verify notification was sent
            assert mock_notify.called
            call_args = mock_notify.call_args[1]
            assert call_args["user_id"] == backtest_task.user.id
            assert call_args["task_id"] == backtest_task.id
            assert call_args["task_name"] == backtest_task.name
            assert call_args["task_type"] == "backtest"
            assert call_args["status"] == TaskStatus.FAILED
            assert call_args["execution_id"] == task_execution.id
            assert "stale lock" in call_args["error_message"].lower()


class TestCleanupWithNoStaleLocks:
    """Test cleanup with no stale locks."""

    def test_cleanup_with_no_running_tasks(self, db):
        """Test cleanup when there are no running tasks."""
        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify no cleanup occurred
        assert result["success"] is True
        assert result["cleaned_count"] == 0
        assert len(result["failed_tasks"]) == 0

    def test_cleanup_with_only_fresh_locks(self, backtest_task, task_execution, lock_manager):
        """Test cleanup when all locks are fresh."""
        # Acquire lock with fresh heartbeat
        lock_manager.acquire_lock(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_id=task_execution.id,
        )

        # Update heartbeat to ensure it's fresh
        lock_manager.update_heartbeat(task_type="backtest", task_id=backtest_task.id)

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify no cleanup occurred
        assert result["success"] is True
        assert result["cleaned_count"] == 0
        assert len(result["failed_tasks"]) == 0

        # Verify task status unchanged
        backtest_task.refresh_from_db()
        assert backtest_task.status == TaskStatus.RUNNING

    def test_cleanup_with_completed_tasks(self, user, strategy_config):
        """Test cleanup ignores completed tasks."""
        # Create completed task
        BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Completed Backtest",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
            instrument="USD_JPY",
            status=TaskStatus.COMPLETED,
        )

        # Run cleanup task
        with patch("trading.services.notifications.send_task_status_notification"):
            result = cleanup_stale_locks_task()

        # Verify no cleanup occurred
        assert result["success"] is True
        assert result["cleaned_count"] == 0
        assert len(result["failed_tasks"]) == 0


class TestErrorHandling:
    """Test error handling in cleanup task."""

    def test_cleanup_continues_on_individual_task_error(self, user, strategy_config, lock_manager):
        """Test that cleanup continues even if one task fails."""
        # Create two running tasks
        task1 = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest 1",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
            instrument="USD_JPY",
            status=TaskStatus.RUNNING,
        )

        task2 = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest 2",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
            instrument="USD_JPY",
            status=TaskStatus.RUNNING,
        )

        # Create executions
        execution1 = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task1.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=10),
        )

        execution2 = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task2.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=10),
        )

        # Make both locks stale
        for task, execution in [(task1, execution1), (task2, execution2)]:
            lock_manager.acquire_lock(
                task_type="backtest",
                task_id=task.id,
                execution_id=execution.id,
            )

            heartbeat_key = lock_manager._get_heartbeat_key("backtest", task.id)
            old_time = timezone.now() - timedelta(seconds=400)
            cache.set(
                heartbeat_key,
                {"last_beat": old_time.isoformat(), "execution_id": execution.id},
                timeout=lock_manager.LOCK_TIMEOUT,
            )

        # Mock get_latest_execution to fail for task1 but succeed for task2
        original_get_latest = BacktestTask.get_latest_execution

        def mock_get_latest(self):
            if self.id == task1.id:
                raise Exception("Simulated error")
            return original_get_latest(self)

        with (
            patch.object(BacktestTask, "get_latest_execution", mock_get_latest),
            patch("trading.services.notifications.send_task_status_notification"),
        ):
            result = cleanup_stale_locks_task()

        # Verify cleanup continued despite error
        assert result["success"] is True
        # At least task2 should be cleaned up
        assert result["cleaned_count"] >= 1

    def test_cleanup_returns_error_on_critical_failure(self):
        """Test that cleanup returns error on critical failure."""
        # Mock BacktestTask.objects.filter to raise exception
        with patch(
            "trading.backtest_task_models.BacktestTask.objects.filter",
            side_effect=Exception("Database error"),
        ):
            result = cleanup_stale_locks_task()

        # Verify error was returned
        assert result["success"] is False
        assert result["cleaned_count"] == 0
        assert "error" in result
        assert result["error"] is not None
