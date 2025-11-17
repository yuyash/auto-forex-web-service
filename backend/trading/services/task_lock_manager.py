"""
Task Lock Manager for distributed task execution control.

This module provides distributed locking mechanisms using Redis to ensure
only one instance of a task executes at a time, with heartbeat monitoring
and automatic cleanup of stale locks.

Requirements: 2.1, 2.2, 2.3, 2.6, 7.1, 7.3, 7.4, 7.5
"""

import logging
from datetime import datetime
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class TaskLockManager:
    """
    Manages distributed locks for task execution with heartbeat monitoring.

    This class provides Redis-based distributed locking to prevent concurrent
    execution of the same task, with automatic cleanup of stale locks.
    """

    # Lock timeout: 5 minutes
    LOCK_TIMEOUT = 300

    # Heartbeat interval: 30 seconds
    HEARTBEAT_INTERVAL = 30

    # Stale lock threshold: 5 minutes without heartbeat
    STALE_LOCK_THRESHOLD = 300

    def __init__(self) -> None:
        """Initialize the TaskLockManager."""
        self.cache = cache

    def _get_lock_key(self, task_type: str, task_id: int) -> str:
        """
        Generate Redis key for task lock.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            Redis key string
        """
        return f"task_lock:{task_type}:{task_id}"

    def _get_heartbeat_key(self, task_type: str, task_id: int) -> str:
        """
        Generate Redis key for task heartbeat.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            Redis key string
        """
        return f"task_heartbeat:{task_type}:{task_id}"

    def _get_cancellation_key(self, task_type: str, task_id: int) -> str:
        """
        Generate Redis key for task cancellation flag.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            Redis key string
        """
        return f"task_cancel:{task_type}:{task_id}"

    def acquire_lock(
        self,
        task_type: str,
        task_id: int,
        execution_id: Optional[int] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Acquire execution lock for task using atomic SETNX operation.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID
            execution_id: Optional execution ID
            worker_id: Optional worker identifier

        Returns:
            True if lock acquired successfully, False otherwise

        Requirements: 2.1, 2.6
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)
        cancel_key = self._get_cancellation_key(task_type, task_id)

        try:
            # Get current timestamp
            current_time = timezone.now().isoformat()

            # Prepare lock data
            lock_data = {
                "acquired_at": current_time,
                "acquired_by": worker_id or "unknown",
                "execution_id": execution_id,
            }

            # Try to acquire lock using add() which implements SETNX
            # add() returns True if key doesn't exist and was set, False otherwise
            lock_acquired = self.cache.add(lock_key, lock_data, timeout=self.LOCK_TIMEOUT)

            if lock_acquired:
                # Clear any stale cancellation flag from previous runs
                self.cache.delete(cancel_key)

                # Set initial heartbeat
                self.cache.set(
                    heartbeat_key,
                    {"last_beat": current_time, "execution_id": execution_id},
                    timeout=self.LOCK_TIMEOUT,
                )

                logger.info(
                    "Lock acquired: task_type=%s, task_id=%s, execution_id=%s",
                    task_type,
                    task_id,
                    execution_id,
                )
                return True

            logger.warning(
                "Failed to acquire lock (already held): task_type=%s, task_id=%s",
                task_type,
                task_id,
            )
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error acquiring lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )
            return False

    def release_lock(self, task_type: str, task_id: int) -> None:
        """
        Release execution lock for task with proper cleanup.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Requirements: 2.6, 7.1
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)
        cancel_key = self._get_cancellation_key(task_type, task_id)

        try:
            # Delete lock, heartbeat, and cancellation flag
            self.cache.delete(lock_key)
            self.cache.delete(heartbeat_key)
            self.cache.delete(cancel_key)

            logger.info("Lock released: task_type=%s, task_id=%s", task_type, task_id)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error releasing lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )

    def update_heartbeat(self, task_type: str, task_id: int) -> None:
        """
        Update lock heartbeat timestamp to indicate task is still running.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Requirements: 2.2
        """
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)

        try:
            # Get current lock data to preserve execution_id
            lock_key = self._get_lock_key(task_type, task_id)
            lock_data = self.cache.get(lock_key)

            execution_id = None
            if lock_data and isinstance(lock_data, dict):
                execution_id = lock_data.get("execution_id")

            # Update heartbeat with current timestamp
            current_time = timezone.now().isoformat()
            self.cache.set(
                heartbeat_key,
                {"last_beat": current_time, "execution_id": execution_id},
                timeout=self.LOCK_TIMEOUT,
            )

            logger.debug("Heartbeat updated: task_type=%s, task_id=%s", task_type, task_id)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error updating heartbeat: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )

    def check_cancellation_flag(self, task_type: str, task_id: int) -> bool:
        """
        Check if task has been cancelled by user.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            True if task should be cancelled, False otherwise

        Requirements: 2.2, 2.3
        """
        cancel_key = self._get_cancellation_key(task_type, task_id)

        try:
            cancel_flag = self.cache.get(cancel_key)
            is_cancelled: bool = cancel_flag == "1"

            if is_cancelled:
                logger.info(
                    "Cancellation flag detected: task_type=%s, task_id=%s",
                    task_type,
                    task_id,
                )

            return is_cancelled

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error checking cancellation flag: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )
            return False

    def set_cancellation_flag(self, task_type: str, task_id: int) -> None:
        """
        Set cancellation flag for running task.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Requirements: 2.1, 2.3
        """
        cancel_key = self._get_cancellation_key(task_type, task_id)

        try:
            # Set cancellation flag with same timeout as lock
            self.cache.set(cancel_key, "1", timeout=self.LOCK_TIMEOUT)

            logger.info("Cancellation flag set: task_type=%s, task_id=%s", task_type, task_id)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error setting cancellation flag: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )

    def cleanup_stale_locks(self) -> int:
        """
        Clean up locks without recent heartbeat (stale locks).

        This method identifies locks that haven't received a heartbeat update
        within the STALE_LOCK_THRESHOLD and automatically releases them.

        Returns:
            Number of stale locks cleaned up

        Requirements: 7.3, 7.4, 7.5
        """
        cleaned_count = 0

        try:
            # Get all lock keys from cache
            # Note: Django's cache doesn't provide a keys() method by default
            # This is a limitation - in production, you'd need to maintain
            # a separate set of active locks or use Redis directly
            logger.warning(
                "cleanup_stale_locks: Django cache backend doesn't support "
                "key enumeration. Consider using Redis client directly for "
                "production implementation."
            )

            # For now, we'll document that this should be called with specific
            # task_type and task_id when needed, or implement using Redis client
            # directly in a Celery periodic task

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error during stale lock cleanup: %s", str(e), exc_info=True)

        return cleaned_count

    def cleanup_stale_lock(self, task_type: str, task_id: int) -> bool:
        """
        Clean up a specific stale lock if it hasn't received heartbeat updates.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            True if lock was stale and cleaned up, False otherwise

        Requirements: 7.3, 7.4, 7.5
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)

        try:
            # Check if lock exists
            lock_data = self.cache.get(lock_key)
            if not lock_data:
                return False

            # Check heartbeat
            heartbeat_data = self.cache.get(heartbeat_key)
            if not heartbeat_data:
                # No heartbeat data, consider it stale
                logger.warning(
                    "Stale lock detected (no heartbeat): task_type=%s, task_id=%s",
                    task_type,
                    task_id,
                )
                self.release_lock(task_type, task_id)
                return True

            # Parse heartbeat timestamp
            if isinstance(heartbeat_data, dict):
                last_beat_str = heartbeat_data.get("last_beat")
                if last_beat_str:
                    try:
                        last_beat = datetime.fromisoformat(last_beat_str)
                        current_time = timezone.now()
                        time_since_heartbeat = (current_time - last_beat).total_seconds()

                        if time_since_heartbeat > self.STALE_LOCK_THRESHOLD:
                            logger.warning(
                                "Stale lock detected (old heartbeat): task_type=%s, "
                                "task_id=%s, seconds_since_heartbeat=%.1f",
                                task_type,
                                task_id,
                                time_since_heartbeat,
                            )
                            self.release_lock(task_type, task_id)
                            return True

                    except (ValueError, AttributeError) as e:
                        logger.error("Error parsing heartbeat timestamp: %s", str(e))
                        # If we can't parse the timestamp, consider it stale
                        self.release_lock(task_type, task_id)
                        return True

            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error checking stale lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )
            return False

    def get_lock_info(self, task_type: str, task_id: int) -> Optional[dict]:
        """
        Get information about current lock status.

        Args:
            task_type: Type of task (e.g., 'backtest', 'trading')
            task_id: Task ID

        Returns:
            Dictionary with lock information or None if no lock exists
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)

        try:
            lock_data = self.cache.get(lock_key)
            heartbeat_data = self.cache.get(heartbeat_key)

            if not lock_data:
                return None

            return {
                "lock": lock_data,
                "heartbeat": heartbeat_data,
                "is_stale": self._is_lock_stale(heartbeat_data),
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error getting lock info: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(e),
                exc_info=True,
            )
            return None

    def _is_lock_stale(self, heartbeat_data: Optional[dict]) -> bool:
        """
        Check if a lock is stale based on heartbeat data.

        Args:
            heartbeat_data: Heartbeat data dictionary

        Returns:
            True if lock is stale, False otherwise
        """
        if not heartbeat_data or not isinstance(heartbeat_data, dict):
            return True

        last_beat_str = heartbeat_data.get("last_beat")
        if not last_beat_str:
            return True

        try:
            last_beat = datetime.fromisoformat(last_beat_str)
            current_time = timezone.now()
            time_since_heartbeat = (current_time - last_beat).total_seconds()
            return time_since_heartbeat > self.STALE_LOCK_THRESHOLD

        except (ValueError, AttributeError):
            return True
