"""Security middleware package exports."""

from typing import Any, List

from apps.accounts.middlewares.limiter import RateLimiter

__all__: List[str] = [
    "HTTPAccessLoggingMiddleware",
    "RateLimiter",
    "SecurityMonitoringMiddleware",
]


def __getattr__(name: str) -> Any:
    """Lazily export middleware classes without importing request logging eagerly."""
    if name == "HTTPAccessLoggingMiddleware":
        from apps.accounts.middlewares.logging import HTTPAccessLoggingMiddleware

        return HTTPAccessLoggingMiddleware
    if name == "SecurityMonitoringMiddleware":
        from apps.accounts.middlewares.security import SecurityMonitoringMiddleware

        return SecurityMonitoringMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
