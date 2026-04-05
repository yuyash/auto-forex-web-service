"""Custom throttle classes for trading views."""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class TaskDataRateThrottle(UserRateThrottle):
    """Higher rate limit for read-heavy task data endpoints (metrics, logs, events)."""

    scope = "task_data"
    FALLBACK_RATE = "600/minute"

    def get_rate(self) -> str:
        """Return configured rate, falling back to FALLBACK_RATE if not set."""
        try:
            return super().get_rate()
        except Exception:
            return self.FALLBACK_RATE
