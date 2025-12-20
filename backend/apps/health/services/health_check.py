from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.db import connections
from django.db.utils import OperationalError


@dataclass(frozen=True)
class HealthCheckResult:
    http_status: int
    body: dict[str, Any]


class HealthCheckService:
    """Performs lightweight health checks for the backend.

    This is intended for container orchestration healthchecks.
    """

    def check(self) -> HealthCheckResult:
        started = time.monotonic()

        database = self._check_database()
        redis = self._check_redis_cache()

        overall_status = self._overall_status(database=database, redis=redis)
        http_status = 200 if overall_status == "healthy" else 503

        body: dict[str, Any] = {
            "overall_status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": database,
                "redis": redis,
            },
            "response_time_ms": int((time.monotonic() - started) * 1000),
        }
        return HealthCheckResult(http_status=http_status, body=body)

    def _check_database(self) -> dict[str, Any]:
        started = time.monotonic()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {
                "status": "healthy",
                "response_time_ms": int((time.monotonic() - started) * 1000),
            }
        except (OperationalError, Exception) as exc:  # pylint: disable=broad-exception-caught
            return {
                "status": "unhealthy",
                "error": str(exc),
                "response_time_ms": int((time.monotonic() - started) * 1000),
            }

    def _check_redis_cache(self) -> dict[str, Any]:
        """Best-effort cache/redis check.

        In tests we often use DummyCache; treat that as "skipped".
        """

        started = time.monotonic()

        cache_backend_value = settings.CACHES.get("default", {}).get("BACKEND", "")
        cache_backend = ""
        if isinstance(cache_backend_value, str):
            cache_backend = cache_backend_value
        # Only treat this as a redis connectivity check when the redis cache backend is configured.
        if "RedisCache" not in cache_backend:
            return {
                "status": "skipped",
                "backend": cache_backend,
                "response_time_ms": int((time.monotonic() - started) * 1000),
            }

        try:
            cache = caches["default"]
            key = "health:ping"
            cache.set(key, "1", timeout=5)
            value = cache.get(key)
            ok = value == "1"
            return {
                "status": "healthy" if ok else "unhealthy",
                "response_time_ms": int((time.monotonic() - started) * 1000),
            }
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return {
                "status": "unhealthy",
                "error": str(exc),
                "response_time_ms": int((time.monotonic() - started) * 1000),
            }

    @staticmethod
    def _overall_status(*, database: dict[str, Any], redis: dict[str, Any]) -> str:
        # Database is required for the backend to function.
        if database.get("status") != "healthy":
            return "unhealthy"

        # Redis is required in production, but some environments may skip it.
        redis_status = redis.get("status")
        if redis_status == "unhealthy":
            return "unhealthy"

        return "healthy"
