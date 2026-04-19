"""Base utilities for market tasks."""

import os
import socket
import threading
from datetime import UTC, datetime
from uuid import uuid4

import redis
from celery import current_task
from django.conf import settings


def current_task_id() -> str | None:
    """Get current Celery task ID."""
    try:
        return str(getattr(getattr(current_task, "request", None), "id", None) or "") or None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def redis_client() -> redis.Redis:
    """Get Redis client for market data."""
    return redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)


def isoformat(dt: datetime) -> str:
    """Convert datetime to ISO format string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO format datetime string."""
    value_str = str(value)
    if value_str.endswith("Z"):
        value_str = value_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(value_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def backtest_stream_key_for_request(request_id: str, execution_id: str | None = None) -> str:
    """Return the Redis Stream key used for delivering backtest ticks.

    A separate stream key per request keeps concurrent backtests isolated.
    When ``execution_id`` is provided, the key is further scoped to that
    execution run so a restarted task never reuses the stream of an older
    (potentially still-draining) execution.  Legacy callers that do not
    pass ``execution_id`` fall back to the task-scoped key.

    The stream is bounded via ``XADD ... MAXLEN ~`` and cleaned up
    explicitly by the publisher when done.
    """
    prefix = getattr(settings, "MARKET_BACKTEST_TICK_STREAM_PREFIX", "market:backtest:stream:")
    if execution_id:
        return f"{prefix}{request_id}:{execution_id}"
    return f"{prefix}{request_id}"


def lock_value() -> str:
    """Get lock value for distributed locking."""
    return f"{socket.gethostname()}:{os.getpid()}"


def new_lock_owner() -> str:
    """Return a unique owner token for a single task run."""
    return f"{lock_value()}:{uuid4().hex}"


def acquire_lock(
    client: redis.Redis,
    key: str,
    ttl_seconds: int,
    *,
    owner: str | None = None,
) -> str | None:
    """Acquire distributed lock using Redis.

    Args:
        client: Redis client
        key: Lock key
        ttl_seconds: Time to live in seconds
        owner: Optional owner token to store

    Returns:
        Owner token if lock acquired, None otherwise
    """
    owner_token = owner or new_lock_owner()
    acquired = client.set(key, owner_token, nx=True, ex=ttl_seconds)
    return owner_token if acquired else None


def refresh_lock_if_owner(
    client: redis.Redis,
    key: str,
    owner: str,
    ttl_seconds: int,
) -> bool:
    """Refresh a lock TTL only when the caller still owns it."""
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("expire", KEYS[1], tonumber(ARGV[2]))
    end
    return 0
    """
    return bool(client.eval(script, 1, key, owner, ttl_seconds))


def release_lock_if_owner(client: redis.Redis, key: str, owner: str | None) -> bool:
    """Release a lock only when the caller owns it."""
    if not owner:
        return False

    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    end
    return 0
    """
    return bool(client.eval(script, 1, key, owner))


class LockHeartbeat:
    """Background TTL refresher for long-running Redis locks."""

    def __init__(
        self,
        *,
        client: redis.Redis,
        key: str,
        owner: str,
        ttl_seconds: int,
        refresh_interval_seconds: float | None = None,
    ) -> None:
        self.client = client
        self.key = key
        self.owner = owner
        self.ttl_seconds = ttl_seconds
        self.refresh_interval_seconds = (
            refresh_interval_seconds
            if refresh_interval_seconds is not None
            else max(float(ttl_seconds) / 3.0, 1.0)
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start background lock refresh."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name=f"lock-heartbeat:{self.key}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background lock refresh."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.refresh_interval_seconds * 2, 1.0))
            self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(self.refresh_interval_seconds):
            try:
                if not refresh_lock_if_owner(
                    self.client,
                    self.key,
                    self.owner,
                    self.ttl_seconds,
                ):
                    return
            except Exception:
                return
