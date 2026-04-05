"""Custom throttle classes for trading views."""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class TaskDataRateThrottle(UserRateThrottle):
    """Higher rate limit for read-heavy task data endpoints (metrics, logs, events)."""

    scope = "task_data"
