"""Base signal definitions and utilities."""

from datetime import UTC, datetime

import redis
from django.conf import settings
from django.dispatch import Signal

# Backtest tick stream signal
# Sent when a backtest needs a historical tick stream.
backtest_tick_stream_requested: Signal = Signal()

# Task cancellation signal
# Sent when some external owner wants a market-managed Celery task to stop cleanly.
market_task_cancel_requested: Signal = Signal()


def redis_client() -> redis.Redis:
    """Get Redis client for market signals."""
    return redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)


def ensure_aware_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware and in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class SignalHandler:
    """Base class for signal handlers."""

    def connect(self) -> None:
        """Connect all signal handlers in this class."""
        raise NotImplementedError("Subclasses must implement connect()")
