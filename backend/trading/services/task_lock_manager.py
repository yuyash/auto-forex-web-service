"""
Task Lock Manager for distributed task execution control.

This module provides distributed locking mechanisms using Redis to ensure
only one instance of a task executes at a time, with heartbeat monitoring
and automatic cleanup of stale locks.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from logging import getLogger
from typing import Any, Optional

from django.core.cache import caches
from django.utils import timezone

from redis import Redis

from trading.enums import TaskType

logger = getLogger(__name__)


@dataclass
class HeartbeatData:
    """
    Data model for task heartbeat information.

    Attributes:
        last_beat: ISO format timestamp of the last heartbeat
        execution_id: Optional execution ID associated with the heartbeat
    """

    last_beat: str
    execution_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HeartbeatData":
        """Create HeartbeatData from dictionary."""
        return cls(
            last_beat=data.get("last_beat", ""),
            execution_id=data.get("execution_id"),
        )


@dataclass
class LockData:
    """
    Data model for task lock information.

    Attributes:
        acquired_at: ISO format timestamp when lock was acquired
        acquired_by: Worker ID that acquired the lock
        execution_id: Optional execution ID associated with the lock
    """

    acquired_at: str
    acquired_by: str
    execution_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LockData":
        """Create LockData from dictionary."""
        return cls(
            acquired_at=data.get("acquired_at", ""),
            acquired_by=data.get("acquired_by", "unknown"),
            execution_id=data.get("execution_id"),
        )


@dataclass
class LockInfo:
    """
    Data model for complete lock status information.

    Attributes:
        lock: Lock data containing acquisition details
        heartbeat: Heartbeat data containing last heartbeat timestamp
        is_stale: Whether the lock is considered stale (no recent heartbeat)
    """

    lock: LockData
    heartbeat: Optional[HeartbeatData]
    is_stale: bool


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

    # Lock key prefix used for Redis SCAN
    LOCK_KEY_PREFIX = "task_lock:"

    def __init__(self) -> None:
        logger.info("Initializing TaskLockManager instance")
        self.cache = caches["default"]

    def acquire_lock(
        self,
        task_type: TaskType,
        task_id: int,
        execution_id: Optional[int] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Acquire execution lock for task using atomic SETNX operation.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID
            execution_id: Optional execution ID
            worker_id: Optional worker identifier

        Returns:
            True if lock acquired successfully, False otherwise
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
                heartbeat = HeartbeatData(
                    last_beat=current_time,
                    execution_id=execution_id,
                )
                self.cache.set(
                    heartbeat_key,
                    heartbeat.to_dict(),
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

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error acquiring lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )
            return False

    def check_cancellation_flag(self, task_type: TaskType, task_id: int) -> bool:
        """
        Check if task has been cancelled by user.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            True if task should be cancelled, False otherwise
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
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error checking cancellation flag: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )
            return False

    def cleanup_stale_lock(self, task_type: TaskType, task_id: int) -> bool:
        """
        Clean up a specific stale lock if it hasn't received heartbeat updates.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            True if lock was stale and cleaned up, False otherwise
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)

        try:
            # Check if lock exists
            lock_data = self.cache.get(lock_key)
            if not lock_data:
                return False

            # Check heartbeat
            heartbeat_dict = self.cache.get(heartbeat_key)
            if not heartbeat_dict:
                # No heartbeat data, consider it stale
                logger.warning(
                    "Stale lock detected (no heartbeat): task_type=%s, task_id=%s",
                    task_type,
                    task_id,
                )
                self.release_lock(task_type, task_id)
                return True

            # Parse heartbeat data
            if isinstance(heartbeat_dict, dict):
                heartbeat = HeartbeatData.from_dict(heartbeat_dict)
                if heartbeat.last_beat:
                    try:
                        last_beat = datetime.fromisoformat(heartbeat.last_beat)
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

                    except (ValueError, AttributeError) as error:
                        logger.error("Error parsing heartbeat timestamp: %s", str(error))
                        # If we can't parse the timestamp, consider it stale
                        self.release_lock(task_type, task_id)
                        return True

            return False

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error checking stale lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )
            return False

    # pylint: disable=too-many-locals
    def cleanup_stale_locks(self, task_type: Optional[TaskType] = None) -> int:
        """
        Clean up locks without recent heartbeat (stale locks).

        This method identifies locks that haven't received a heartbeat update
        within the STALE_LOCK_THRESHOLD and automatically releases them.

        Uses Redis SCAN command to find all lock keys matching the pattern,
        which is non-blocking and production-safe.

        Args:
            task_type: Optional task type to filter locks. If None, cleans all task types.

        Returns:
            Number of stale locks cleaned up
        """
        cleaned_count = 0

        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning(
                    "cleanup_stale_locks: Could not get Redis client. "
                    "Ensure Redis cache backend is properly configured."
                )
                return 0

            # Get the key prefix used by Django's cache
            # Django prepends KEY_PREFIX and version to all keys
            key_prefix = self.cache.key_prefix
            version = self.cache.version

            # Build the pattern to match lock keys
            # Django key format: ":version:KEY_PREFIX:actual_key"
            if task_type:
                pattern = f":{version}:{key_prefix}:task_lock:{task_type.value}:*"
            else:
                pattern = f":{version}:{key_prefix}:task_lock:*"

            logger.info("Scanning for stale locks with pattern: %s", pattern)

            # Use SCAN to iterate through keys (non-blocking, production-safe)
            cursor = 0
            lock_keys_found = 0

            while True:
                cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
                lock_keys_found += len(keys)

                for full_key in keys:
                    # Decode the key if it's bytes
                    if isinstance(full_key, bytes):
                        full_key = full_key.decode("utf-8")

                    # Extract task_type and task_id from the key
                    # Key format: ":version:KEY_PREFIX:task_lock:task_type:task_id"
                    parsed = self._parse_lock_key(full_key)
                    if parsed is None:
                        continue

                    extracted_task_type, extracted_task_id = parsed

                    # Check if this specific lock is stale
                    if self.cleanup_stale_lock(extracted_task_type, extracted_task_id):
                        cleaned_count += 1

                # SCAN returns 0 when iteration is complete
                if cursor == 0:
                    break

            logger.info(
                "Stale lock cleanup completed: found=%d, cleaned=%d",
                lock_keys_found,
                cleaned_count,
            )

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Error during stale lock cleanup: %s", str(error), exc_info=True)

        return cleaned_count

    def get_lock_info(self, task_type: TaskType, task_id: int) -> Optional[LockInfo]:
        """
        Get information about current lock status.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            LockInfo object with lock information or None if no lock exists
        """
        lock_key = self._get_lock_key(task_type, task_id)
        heartbeat_key = self._get_heartbeat_key(task_type, task_id)

        try:
            lock_dict = self.cache.get(lock_key)
            heartbeat_dict = self.cache.get(heartbeat_key)

            if not lock_dict:
                return None

            lock_data = LockData.from_dict(lock_dict) if isinstance(lock_dict, dict) else None
            if not lock_data:
                return None

            heartbeat: Optional[HeartbeatData] = None
            if isinstance(heartbeat_dict, dict):
                heartbeat = HeartbeatData.from_dict(heartbeat_dict)

            return LockInfo(
                lock=lock_data,
                heartbeat=heartbeat,
                is_stale=self._is_lock_stale(heartbeat),
            )

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error getting lock info: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )
            return None

    def release_lock(self, task_type: TaskType, task_id: int) -> None:
        """
        Release execution lock for task with proper cleanup.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID
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

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error releasing lock: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )

    def set_cancellation_flag(self, task_type: TaskType, task_id: int) -> None:
        """
        Set cancellation flag for running task.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID
        """
        cancel_key = self._get_cancellation_key(task_type, task_id)

        try:
            # Set cancellation flag with same timeout as lock
            self.cache.set(cancel_key, "1", timeout=self.LOCK_TIMEOUT)

            logger.info("Cancellation flag set: task_type=%s, task_id=%s", task_type, task_id)

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error setting cancellation flag: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )

    def update_heartbeat(self, task_type: TaskType, task_id: int) -> None:
        """
        Update lock heartbeat timestamp to indicate task is still running.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID
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
            heartbeat = HeartbeatData(
                last_beat=current_time,
                execution_id=execution_id,
            )
            self.cache.set(
                heartbeat_key,
                heartbeat.to_dict(),
                timeout=self.LOCK_TIMEOUT,
            )

            logger.debug("Heartbeat updated: task_type=%s, task_id=%s", task_type, task_id)

        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error updating heartbeat: task_type=%s, task_id=%s, error=%s",
                task_type,
                task_id,
                str(error),
                exc_info=True,
            )

    def _get_cancellation_key(self, task_type: TaskType, task_id: int) -> str:
        """
        Generate Redis key for task cancellation flag.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            Redis key string
        """
        cancel_key = f"task_cancel:{task_type.value}:{task_id}"
        logger.debug("Generated cancellation key: %s", cancel_key)
        return cancel_key

    def _get_heartbeat_key(self, task_type: TaskType, task_id: int) -> str:
        """
        Generate Redis key for task heartbeat.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            Redis key string
        """
        heartbeat_key = f"task_heartbeat:{task_type.value}:{task_id}"
        logger.debug("Generated heartbeat key: %s", heartbeat_key)
        return heartbeat_key

    def _get_lock_key(self, task_type: TaskType, task_id: int) -> str:
        """
        Generate Redis key for task lock.

        Args:
            task_type: Type of task (TaskType.BACKTEST or TaskType.TRADING)
            task_id: Task ID

        Returns:
            Redis key string
        """
        lock_key = f"task_lock:{task_type.value}:{task_id}"
        logger.debug("Generated lock key: %s", lock_key)
        return lock_key

    def _get_redis_client(self) -> Optional[Redis]:
        """
        Get the underlying Redis client from Django's cache.

        Returns:
            Redis client instance or None if unavailable
        """
        try:
            # Access the internal RedisCacheClient and get the raw Redis connection
            # The _cache attribute is Django's internal cache client implementation
            cache_client = getattr(self.cache, "_cache", None)
            if cache_client and hasattr(cache_client, "get_client"):
                client = cache_client.get_client(None)
                if isinstance(client, Redis):
                    return client
            return None
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Could not get Redis client: %s", str(error))
            return None

    def _is_lock_stale(self, heartbeat: Optional[HeartbeatData]) -> bool:
        """
        Check if a lock is stale based on heartbeat data.

        Args:
            heartbeat: HeartbeatData instance

        Returns:
            True if lock is stale, False otherwise
        """
        if not heartbeat or not heartbeat.last_beat:
            return True

        try:
            last_beat = datetime.fromisoformat(heartbeat.last_beat)
            current_time = timezone.now()
            time_since_heartbeat = (current_time - last_beat).total_seconds()
            return time_since_heartbeat > self.STALE_LOCK_THRESHOLD
        except (ValueError, AttributeError):
            return True

    def _parse_lock_key(self, full_key: str) -> Optional[tuple[TaskType, int]]:
        """
        Parse a lock key to extract task type and task ID.

        Args:
            full_key: Full Redis key string

        Returns:
            Tuple of (TaskType, task_id) or None if parsing fails
        """
        try:
            parts = full_key.split(":")
            # Expected: ['', 'version', 'KEY_PREFIX', 'task_lock', 'type', 'id']
            if len(parts) < 6:
                return None

            extracted_task_type_str = parts[-2]
            extracted_task_id = int(parts[-1])

            # Convert string to TaskType enum
            try:
                extracted_task_type = TaskType(extracted_task_type_str)
            except ValueError:
                logger.warning(
                    "Unknown task type '%s' in lock key '%s'",
                    extracted_task_type_str,
                    full_key,
                )
                return None

            return (extracted_task_type, extracted_task_id)

        except (ValueError, IndexError) as error:
            logger.warning("Could not parse lock key '%s': %s", full_key, str(error))
            return None
