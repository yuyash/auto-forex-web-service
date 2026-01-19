from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from logging import Logger, getLogger
from typing import Any, Literal

from django.conf import settings
from django.core.cache import caches
from django.db import connections
from django.db.utils import OperationalError

logger: Logger = getLogger(name=__name__)


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class HealthCheckResult:
    http_status: int
    body: dict[str, Any]


@dataclass(frozen=True)
class ComponentCheckResult:
    """Result of a single component health check."""

    status: HealthStatus
    response_time_ms: int
    error: str | None = None
    backend: str | None = None


class HealthCheckService:
    """Performs system health checks for the backend.

    This is mainly intended for container health checks.
    """

    def check(self) -> HealthCheckResult:
        started: float = time.monotonic()
        logger.info(msg="Starting health check")

        database: ComponentCheckResult = self._check_database()
        redis: ComponentCheckResult = self._check_redis_cache()

        # Determine overall status based on all checks
        status: HealthStatus = self._determine_status(database=database, redis=redis)
        http_status: Literal[200, 503] = 200 if status == HealthStatus.HEALTHY else 503

        response_time_ms = int((time.monotonic() - started) * 1000)

        body: dict[str, Any] = {
            "status": status.value,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "response_time_ms": response_time_ms,
        }

        logger.info(
            msg=f"Health check completed: status={status.value}, "
            f"database={database.status.value}, "
            f"redis={redis.status.value}, "
            f"response_time_ms={response_time_ms}"
        )

        return HealthCheckResult(http_status=http_status, body=body)

    def _check_database(self) -> ComponentCheckResult:
        started: float = time.monotonic()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute(sql="SELECT 1")
                cursor.fetchone()
            response_time_ms = int((time.monotonic() - started) * 1000)
            logger.debug(msg=f"Database check passed: response_time_ms={response_time_ms}")
            return ComponentCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
            )
        except (OperationalError, Exception) as exc:  # pylint: disable=broad-exception-caught
            response_time_ms = int((time.monotonic() - started) * 1000)
            logger.error(msg=f"Database check failed: {exc}, response_time_ms={response_time_ms}")
            return ComponentCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(object=exc),
            )

    def _check_redis_cache(self) -> ComponentCheckResult:
        """Best-effort cache/redis check.

        In tests we often use DummyCache; treat that as "skipped".
        """

        started: float = time.monotonic()
        cache_backend_value = settings.CACHES.get("default", {}).get("BACKEND", "")
        cache_backend = ""
        if isinstance(cache_backend_value, str):
            cache_backend = cache_backend_value
        # Only treat this as a redis connectivity check when the redis cache backend is configured.
        if "RedisCache" not in cache_backend:
            response_time_ms = int((time.monotonic() - started) * 1000)
            logger.debug(f"Redis check skipped: backend={cache_backend}")
            return ComponentCheckResult(
                status=HealthStatus.SKIPPED,
                response_time_ms=response_time_ms,
                backend=cache_backend,
            )

        try:
            cache = caches["default"]
            key = "health:ping"
            cache.set(key, "1", timeout=5)
            value = cache.get(key)
            ok = value == "1"
            response_time_ms = int((time.monotonic() - started) * 1000)
            status = HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
            logger.debug(
                f"Redis check completed: status={status.value}, response_time_ms={response_time_ms}"
            )
            return ComponentCheckResult(
                status=status,
                response_time_ms=response_time_ms,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            response_time_ms = int((time.monotonic() - started) * 1000)
            logger.error(f"Redis check failed: {exc}, response_time_ms={response_time_ms}")
            return ComponentCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error=str(exc),
            )

    @staticmethod
    def _determine_status(
        *, database: ComponentCheckResult, redis: ComponentCheckResult
    ) -> HealthStatus:
        """Determine overall health status based on all checks.

        Args:
            database: Database check result
            redis: Redis check result

        Returns:
            HealthStatus.HEALTHY if all required checks pass, HealthStatus.UNHEALTHY otherwise
        """
        # Database is required for the backend to function.
        if database.status != HealthStatus.HEALTHY:
            return HealthStatus.UNHEALTHY

        # Redis is required in production, but some environments may skip it.
        if redis.status == HealthStatus.UNHEALTHY:
            return HealthStatus.UNHEALTHY

        return HealthStatus.HEALTHY
