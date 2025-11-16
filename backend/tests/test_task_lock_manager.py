"""
Unit tests for TaskLockManager service.

Tests the TaskLockManager distributed locking mechanism including:
- Lock acquisition success and failure scenarios
- Heartbeat update mechanism
- Cancellation flag detection
- Stale lock cleanup with various timeout scenarios
- Concurrent lock acquisition attempts

Requirements: 2.1, 2.2, 2.3, 2.6
"""

import time
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

import pytest

from trading.services.task_lock_manager import TaskLockManager


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


class TestLockAcquisition:
    """Test lock acquisition scenarios."""

    def test_acquire_lock_success(self, lock_manager):
        """Test successful lock acquisition."""
        # Acquire lock
        result = lock_manager.acquire_lock(
            task_type="backtest",
            task_id=1,
            execution_id=100,
            worker_id="worker-1",
        )

        assert result is True

        # Verify lock data is stored
        lock_key = lock_manager._get_lock_key("backtest", 1)
        lock_data = cache.get(lock_key)

        assert lock_data is not None
        assert lock_data["acquired_by"] == "worker-1"
        assert lock_data["execution_id"] == 100
        assert "acquired_at" in lock_data

    def test_acquire_lock_failure_already_held(self, lock_manager):
        """Test lock acquisition failure when lock is already held."""
        # First acquisition succeeds
        result1 = lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)
        assert result1 is True

        # Second acquisition fails
        result2 = lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=101)
        assert result2 is False

    def test_acquire_lock_different_tasks(self, lock_manager):
        """Test acquiring locks for different tasks succeeds."""
        # Acquire lock for task 1
        result1 = lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)
        assert result1 is True

        # Acquire lock for task 2 (different task)
        result2 = lock_manager.acquire_lock(task_type="backtest", task_id=2, execution_id=101)
        assert result2 is True

    def test_acquire_lock_different_task_types(self, lock_manager):
        """Test acquiring locks for different task types succeeds."""
        # Acquire lock for backtest task
        result1 = lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)
        assert result1 is True

        # Acquire lock for trading task (same ID, different type)
        result2 = lock_manager.acquire_lock(task_type="trading", task_id=1, execution_id=101)
        assert result2 is True

    def test_acquire_lock_sets_heartbeat(self, lock_manager):
        """Test that acquiring lock also sets initial heartbeat."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Verify heartbeat is set
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        heartbeat_data = cache.get(heartbeat_key)

        assert heartbeat_data is not None
        assert "last_beat" in heartbeat_data
        assert heartbeat_data["execution_id"] == 100


class TestLockRelease:
    """Test lock release scenarios."""

    def test_release_lock_success(self, lock_manager):
        """Test successful lock release."""
        # Acquire lock first
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Release lock
        lock_manager.release_lock(task_type="backtest", task_id=1)

        # Verify lock is removed
        lock_key = lock_manager._get_lock_key("backtest", 1)
        lock_data = cache.get(lock_key)
        assert lock_data is None

        # Verify heartbeat is removed
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        heartbeat_data = cache.get(heartbeat_key)
        assert heartbeat_data is None

    def test_release_lock_removes_cancellation_flag(self, lock_manager):
        """Test that releasing lock also removes cancellation flag."""
        # Acquire lock and set cancellation flag
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)
        lock_manager.set_cancellation_flag(task_type="backtest", task_id=1)

        # Release lock
        lock_manager.release_lock(task_type="backtest", task_id=1)

        # Verify cancellation flag is removed
        cancel_key = lock_manager._get_cancellation_key("backtest", 1)
        cancel_flag = cache.get(cancel_key)
        assert cancel_flag is None

    def test_release_nonexistent_lock(self, lock_manager):
        """Test releasing a lock that doesn't exist (should not raise error)."""
        # Should not raise any exception
        lock_manager.release_lock(task_type="backtest", task_id=999)

    def test_reacquire_after_release(self, lock_manager):
        """Test that lock can be reacquired after release."""
        # Acquire and release
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)
        lock_manager.release_lock(task_type="backtest", task_id=1)

        # Reacquire should succeed
        result = lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=101)
        assert result is True


class TestHeartbeat:
    """Test heartbeat update mechanism."""

    def test_update_heartbeat_success(self, lock_manager):
        """Test successful heartbeat update."""
        # Acquire lock first
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Get initial heartbeat
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        initial_heartbeat = cache.get(heartbeat_key)
        initial_time = initial_heartbeat["last_beat"]

        # Wait a bit and update heartbeat
        time.sleep(0.1)
        lock_manager.update_heartbeat(task_type="backtest", task_id=1)

        # Get updated heartbeat
        updated_heartbeat = cache.get(heartbeat_key)
        updated_time = updated_heartbeat["last_beat"]

        # Verify heartbeat was updated
        assert updated_time > initial_time
        assert updated_heartbeat["execution_id"] == 100

    def test_update_heartbeat_preserves_execution_id(self, lock_manager):
        """Test that heartbeat update preserves execution_id."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Update heartbeat multiple times
        for _ in range(3):
            lock_manager.update_heartbeat(task_type="backtest", task_id=1)

        # Verify execution_id is still preserved
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        heartbeat_data = cache.get(heartbeat_key)
        assert heartbeat_data["execution_id"] == 100

    def test_update_heartbeat_without_lock(self, lock_manager):
        """Test updating heartbeat when no lock exists (should not raise error)."""
        # Should not raise any exception
        lock_manager.update_heartbeat(task_type="backtest", task_id=999)


class TestCancellationFlag:
    """Test cancellation flag mechanism."""

    def test_set_cancellation_flag(self, lock_manager):
        """Test setting cancellation flag."""
        # Set cancellation flag
        lock_manager.set_cancellation_flag(task_type="backtest", task_id=1)

        # Verify flag is set
        cancel_key = lock_manager._get_cancellation_key("backtest", 1)
        cancel_flag = cache.get(cancel_key)
        assert cancel_flag == "1"

    def test_check_cancellation_flag_true(self, lock_manager):
        """Test checking cancellation flag when set."""
        # Set cancellation flag
        lock_manager.set_cancellation_flag(task_type="backtest", task_id=1)

        # Check flag
        is_cancelled = lock_manager.check_cancellation_flag(task_type="backtest", task_id=1)
        assert is_cancelled is True

    def test_check_cancellation_flag_false(self, lock_manager):
        """Test checking cancellation flag when not set."""
        # Check flag without setting it
        is_cancelled = lock_manager.check_cancellation_flag(task_type="backtest", task_id=1)
        assert is_cancelled is False

    def test_cancellation_flag_workflow(self, lock_manager):
        """Test complete cancellation workflow."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Initially not cancelled
        assert lock_manager.check_cancellation_flag("backtest", 1) is False

        # Set cancellation flag
        lock_manager.set_cancellation_flag(task_type="backtest", task_id=1)

        # Now should be cancelled
        assert lock_manager.check_cancellation_flag("backtest", 1) is True

        # Release lock (should clear flag)
        lock_manager.release_lock(task_type="backtest", task_id=1)

        # Flag should be cleared
        assert lock_manager.check_cancellation_flag("backtest", 1) is False


class TestStaleLockCleanup:
    """Test stale lock cleanup mechanism."""

    def test_cleanup_stale_lock_with_old_heartbeat(self, lock_manager):
        """Test cleanup of lock with old heartbeat."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Manually set old heartbeat (simulate stale lock)
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        old_time = timezone.now() - timedelta(seconds=400)  # 6+ minutes ago
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": 100},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Cleanup stale lock
        was_stale = lock_manager.cleanup_stale_lock(task_type="backtest", task_id=1)
        assert was_stale is True

        # Verify lock was released
        lock_key = lock_manager._get_lock_key("backtest", 1)
        lock_data = cache.get(lock_key)
        assert lock_data is None

    def test_cleanup_stale_lock_with_no_heartbeat(self, lock_manager):
        """Test cleanup of lock with no heartbeat data."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Remove heartbeat (simulate missing heartbeat)
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        cache.delete(heartbeat_key)

        # Cleanup stale lock
        was_stale = lock_manager.cleanup_stale_lock(task_type="backtest", task_id=1)
        assert was_stale is True

        # Verify lock was released
        lock_key = lock_manager._get_lock_key("backtest", 1)
        lock_data = cache.get(lock_key)
        assert lock_data is None

    def test_cleanup_fresh_lock_not_removed(self, lock_manager):
        """Test that fresh lock with recent heartbeat is not removed."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Update heartbeat to ensure it's fresh
        lock_manager.update_heartbeat(task_type="backtest", task_id=1)

        # Try to cleanup (should not remove fresh lock)
        was_stale = lock_manager.cleanup_stale_lock(task_type="backtest", task_id=1)
        assert was_stale is False

        # Verify lock still exists
        lock_key = lock_manager._get_lock_key("backtest", 1)
        lock_data = cache.get(lock_key)
        assert lock_data is not None

    def test_cleanup_nonexistent_lock(self, lock_manager):
        """Test cleanup of lock that doesn't exist."""
        # Try to cleanup non-existent lock
        was_stale = lock_manager.cleanup_stale_lock(task_type="backtest", task_id=999)
        assert was_stale is False


class TestLockInfo:
    """Test lock information retrieval."""

    def test_get_lock_info_with_active_lock(self, lock_manager):
        """Test getting info for active lock."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Get lock info
        info = lock_manager.get_lock_info(task_type="backtest", task_id=1)

        assert info is not None
        assert "lock" in info
        assert "heartbeat" in info
        assert "is_stale" in info
        assert info["lock"]["execution_id"] == 100
        assert info["is_stale"] is False

    def test_get_lock_info_nonexistent_lock(self, lock_manager):
        """Test getting info for non-existent lock."""
        # Get info for non-existent lock
        info = lock_manager.get_lock_info(task_type="backtest", task_id=999)
        assert info is None

    def test_get_lock_info_stale_lock(self, lock_manager):
        """Test getting info for stale lock."""
        # Acquire lock
        lock_manager.acquire_lock(task_type="backtest", task_id=1, execution_id=100)

        # Make heartbeat stale
        heartbeat_key = lock_manager._get_heartbeat_key("backtest", 1)
        old_time = timezone.now() - timedelta(seconds=400)
        cache.set(
            heartbeat_key,
            {"last_beat": old_time.isoformat(), "execution_id": 100},
            timeout=lock_manager.LOCK_TIMEOUT,
        )

        # Get lock info
        info = lock_manager.get_lock_info(task_type="backtest", task_id=1)

        assert info is not None
        assert info["is_stale"] is True


class TestConcurrentAccess:
    """Test concurrent lock acquisition scenarios."""

    def test_concurrent_acquisition_only_one_succeeds(self, lock_manager):
        """Test that only one concurrent acquisition succeeds."""
        # Simulate concurrent acquisitions
        results = []
        for i in range(5):
            result = lock_manager.acquire_lock(
                task_type="backtest", task_id=1, execution_id=100 + i
            )
            results.append(result)

        # Only first acquisition should succeed
        assert results[0] is True
        assert all(r is False for r in results[1:])

    def test_sequential_acquisition_after_release(self, lock_manager):
        """Test sequential acquisitions after releases."""
        # Multiple acquire-release cycles
        for i in range(3):
            # Acquire
            result = lock_manager.acquire_lock(
                task_type="backtest", task_id=1, execution_id=100 + i
            )
            assert result is True

            # Release
            lock_manager.release_lock(task_type="backtest", task_id=1)

            # Verify lock is released
            lock_key = lock_manager._get_lock_key("backtest", 1)
            assert cache.get(lock_key) is None


class TestKeyGeneration:
    """Test Redis key generation methods."""

    def test_lock_key_format(self, lock_manager):
        """Test lock key format."""
        key = lock_manager._get_lock_key("backtest", 123)
        assert key == "task_lock:backtest:123"

    def test_heartbeat_key_format(self, lock_manager):
        """Test heartbeat key format."""
        key = lock_manager._get_heartbeat_key("trading", 456)
        assert key == "task_heartbeat:trading:456"

    def test_cancellation_key_format(self, lock_manager):
        """Test cancellation key format."""
        key = lock_manager._get_cancellation_key("backtest", 789)
        assert key == "task_cancel:backtest:789"
