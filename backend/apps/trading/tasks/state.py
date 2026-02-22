"""State management for task execution.

This module provides centralized state management for task coordination
via Redis, including heartbeats, control signals, and lifecycle tracking.
"""

from __future__ import annotations

import json
import logging
import time
from logging import Logger
from typing import Any

import redis
from django.conf import settings

from apps.trading.dataclasses import TaskControl
from apps.trading.enums import TaskStatus

logger: Logger = logging.getLogger(name=__name__)


class StateManager:
    """Manages task state coordination via Redis.

    Handles heartbeats, stop signals, and task lifecycle state in Redis
    with throttling and TTL management.
    """

    def __init__(
        self,
        *,
        task_name: str,
        instance_key: str,
        task_id: int,
        redis_url: str | None = None,
        stop_check_interval_seconds: float = 1.0,
        heartbeat_interval_seconds: float = 5.0,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialize the state manager.

        Args:
            task_name: Task name (e.g., "trading.tasks.run_backtest_task")
            instance_key: Unique instance identifier (typically task PK)
            task_id: Task database ID
            redis_url: Redis URL (defaults to MARKET_REDIS_URL from settings)
            stop_check_interval_seconds: How often to check for stop signals
            heartbeat_interval_seconds: How often to send heartbeats
            ttl_seconds: Time to live for task state in Redis
        """
        self.task_name = task_name
        self.instance_key = instance_key
        self.task_id = task_id
        self.stop_check_interval_seconds = float(stop_check_interval_seconds)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self.ttl_seconds = int(ttl_seconds)

        # Redis key for this task instance
        self.redis_key = f"task:coord:{task_name}:{instance_key}"

        # Redis client
        url = redis_url or settings.MARKET_REDIS_URL
        self.redis = redis.Redis.from_url(url, decode_responses=True)

        # Throttling state
        self._last_stop_check = 0.0
        self._cached_should_stop = False
        self._last_heartbeat = 0.0

    def start(
        self,
        *,
        celery_task_id: str | None = None,
        worker: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Start task coordination in Redis.

        Args:
            celery_task_id: Celery task ID
            worker: Worker hostname
            meta: Additional metadata
        """
        now = time.time()
        state = {
            "status": "running",
            "celery_task_id": celery_task_id or "",
            "worker": worker or "",
            "started_at": now,
            "last_heartbeat_at": now,
            "stopped_at": "",
            "status_message": "",
            "meta": json.dumps(meta or {}),
        }

        self.redis.hset(self.redis_key, mapping=state)
        self.redis.expire(self.redis_key, self.ttl_seconds)

    def heartbeat(
        self,
        *,
        status_message: str | None = None,
        meta_update: dict[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        """Send heartbeat (throttled).

        Args:
            status_message: Optional status message
            meta_update: Optional metadata updates
            force: If True, bypass throttling
        """
        now = time.monotonic()
        if not force and (now - self._last_heartbeat) < self.heartbeat_interval_seconds:
            return

        updates: dict[str, str | float] = {"last_heartbeat_at": time.time()}

        if status_message is not None:
            updates["status_message"] = status_message

        if meta_update is not None:
            existing_meta_str = self.redis.hget(self.redis_key, "meta") or "{}"
            try:
                existing_meta = json.loads(existing_meta_str)
            except (json.JSONDecodeError, TypeError):
                existing_meta = {}
            merged_meta = {**existing_meta, **meta_update}
            updates["meta"] = json.dumps(merged_meta)

        # Type ignore for Redis stubs - our dict is compatible
        self.redis.hset(self.redis_key, mapping=updates)  # type: ignore[arg-type]
        self.redis.expire(self.redis_key, self.ttl_seconds)
        self._last_heartbeat = now

    def check_control(self, *, force: bool = False) -> TaskControl:
        """Check for stop signals (throttled).

        Args:
            force: If True, bypass throttling

        Returns:
            TaskControl: Control flags
        """
        now = time.monotonic()
        if not force and (now - self._last_stop_check) < self.stop_check_interval_seconds:
            return TaskControl(should_stop=self._cached_should_stop)

        # Check Redis
        redis_status = self.redis.hget(self.redis_key, "status")
        should_stop_redis = redis_status == "stopping"

        # Check database (fallback)
        try:
            from apps.trading.models import BacktestTask, TradingTask

            task = (
                BacktestTask.objects.filter(pk=self.task_id)
                .values_list("status", flat=True)
                .first()
            )
            if task is None:
                task = (
                    TradingTask.objects.filter(pk=self.task_id)
                    .values_list("status", flat=True)
                    .first()
                )

            should_stop_db = task == TaskStatus.STOPPING
        except Exception:
            should_stop_db = False

        self._cached_should_stop = should_stop_redis or should_stop_db
        self._last_stop_check = now

        return TaskControl(should_stop=self._cached_should_stop)

    def stop(
        self,
        *,
        status_message: str | None = None,
        failed: bool = False,
        completed: bool = False,
    ) -> None:
        """Mark task as stopped in Redis.

        Args:
            status_message: Optional message
            failed: If True, mark as failed
            completed: If True, mark as completed (takes precedence over failed)
        """
        if completed:
            status = "completed"
        elif failed:
            status = "failed"
        else:
            status = "stopped"

        now = time.time()
        updates: dict[str, str | float] = {
            "status": status,
            "stopped_at": now,
            "last_heartbeat_at": now,
        }

        if status_message is not None:
            updates["status_message"] = status_message

        # Type ignore for Redis stubs - our dict is compatible
        self.redis.hset(self.redis_key, mapping=updates)  # type: ignore[arg-type]
        self.redis.expire(self.redis_key, 300)  # 5 min cleanup

    def cleanup(self) -> None:
        """Cleanup Redis resources."""
        try:
            self.redis.delete(self.redis_key)
        except Exception:  # nosec
            pass
        finally:
            try:
                self.redis.close()
            except Exception:  # nosec
                pass
