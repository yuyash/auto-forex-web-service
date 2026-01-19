"""Base utilities for market tasks."""

import os
import socket
from datetime import UTC, datetime

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


def backtest_channel_for_request(request_id: str) -> str:
    """Get Redis channel name for backtest request."""
    prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
    return f"{prefix}{request_id}"


def lock_value() -> str:
    """Get lock value for distributed locking."""
    return f"{socket.gethostname()}:{os.getpid()}"


def acquire_lock(client: redis.Redis, key: str, ttl_seconds: int) -> bool:
    """Acquire distributed lock using Redis.

    Args:
        client: Redis client
        key: Lock key
        ttl_seconds: Time to live in seconds

    Returns:
        True if lock acquired, False otherwise
    """
    return bool(client.set(key, lock_value(), nx=True, ex=ttl_seconds))
