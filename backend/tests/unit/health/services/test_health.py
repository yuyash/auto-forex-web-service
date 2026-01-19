"""Unit tests for health check service."""

from unittest.mock import Mock, patch

from django.db import OperationalError
from django.test import override_settings

from apps.health.services.health import (
    ComponentCheckResult,
    HealthCheckResult,
    HealthCheckService,
    HealthStatus,
)


class TestHealthCheckService:
    """Test HealthCheckService class."""

    @patch("apps.health.services.health.connections")
    def test_check_database_success(self, mock_connections):
        """Test database check succeeds."""
        mock_cursor = Mock()
        mock_connections.__getitem__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        service = HealthCheckService()
        result = service._check_database()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms >= 0
        assert result.error is None
        mock_cursor.execute.assert_called_once_with(sql="SELECT 1")

    @patch("apps.health.services.health.connections")
    def test_check_database_failure(self, mock_connections):
        """Test database check handles failure."""
        mock_connections.__getitem__.return_value.cursor.side_effect = OperationalError(
            "Connection failed"
        )

        service = HealthCheckService()
        result = service._check_database()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Connection failed"

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_healthy_status(self, mock_redis, mock_db):
        """Test check returns healthy status when all checks pass."""
        mock_db.return_value = ComponentCheckResult(
            status=HealthStatus.HEALTHY, response_time_ms=10
        )
        mock_redis.return_value = ComponentCheckResult(
            status=HealthStatus.HEALTHY, response_time_ms=5
        )

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 200
        assert result.body["status"] == HealthStatus.HEALTHY.value
        assert "timestamp" in result.body
        assert "response_time_ms" in result.body
        assert "checks" not in result.body  # checks field removed

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_unhealthy_status(self, mock_redis, mock_db):
        """Test check returns unhealthy status when database fails."""
        mock_db.return_value = ComponentCheckResult(
            status=HealthStatus.UNHEALTHY, response_time_ms=10, error="Connection failed"
        )
        mock_redis.return_value = ComponentCheckResult(
            status=HealthStatus.HEALTHY, response_time_ms=5
        )

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 503
        assert result.body["status"] == HealthStatus.UNHEALTHY.value

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_unhealthy_when_redis_fails(self, mock_redis, mock_db):
        """Test check returns unhealthy status when redis fails."""
        mock_db.return_value = ComponentCheckResult(
            status=HealthStatus.HEALTHY, response_time_ms=10
        )
        mock_redis.return_value = ComponentCheckResult(
            status=HealthStatus.UNHEALTHY, response_time_ms=5, error="Redis connection failed"
        )

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 503
        assert result.body["status"] == HealthStatus.UNHEALTHY.value

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_healthy_when_redis_skipped(self, mock_redis, mock_db):
        """Test check returns healthy status when redis is skipped."""
        mock_db.return_value = ComponentCheckResult(
            status=HealthStatus.HEALTHY, response_time_ms=10
        )
        mock_redis.return_value = ComponentCheckResult(
            status=HealthStatus.SKIPPED, response_time_ms=1, backend="DummyCache"
        )

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 200
        assert result.body["status"] == HealthStatus.HEALTHY.value


class TestRedisHealthCheck:
    """Test Redis health check functionality."""

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://localhost:6379/1",
            }
        }
    )
    @patch("apps.health.services.health.caches")
    def test_check_redis_cache_success(self, mock_caches: Mock) -> None:
        """Test Redis check succeeds when cache operations work."""
        mock_cache = Mock()
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "1"
        mock_caches.__getitem__.return_value = mock_cache

        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms >= 0
        assert result.error is None
        mock_cache.set.assert_called_once_with("health:ping", "1", timeout=5)
        mock_cache.get.assert_called_once_with("health:ping")

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://localhost:6379/1",
            }
        }
    )
    @patch("apps.health.services.health.caches")
    def test_check_redis_cache_value_mismatch(self, mock_caches: Mock) -> None:
        """Test Redis check fails when cached value doesn't match."""
        mock_cache = Mock()
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "wrong_value"
        mock_caches.__getitem__.return_value = mock_cache

        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.UNHEALTHY
        assert result.response_time_ms >= 0

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://localhost:6379/1",
            }
        }
    )
    @patch("apps.health.services.health.caches")
    def test_check_redis_cache_connection_failure(self, mock_caches: Mock) -> None:
        """Test Redis check handles connection failure."""
        mock_cache = Mock()
        mock_cache.set.side_effect = Exception("Connection refused")
        mock_caches.__getitem__.return_value = mock_cache

        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Connection refused"
        assert result.response_time_ms >= 0

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
            }
        }
    )
    def test_check_redis_cache_skipped_with_dummy_cache(self) -> None:
        """Test Redis check is skipped when DummyCache is configured."""
        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.SKIPPED
        assert result.response_time_ms >= 0
        assert result.backend is not None
        assert "DummyCache" in result.backend

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_check_redis_cache_skipped_with_locmem_cache(self) -> None:
        """Test Redis check is skipped when LocMemCache is configured."""
        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.SKIPPED
        assert result.response_time_ms >= 0
        assert result.backend is not None
        assert "LocMemCache" in result.backend

    @override_settings(CACHES={"default": {}})
    def test_check_redis_cache_skipped_with_no_backend(self) -> None:
        """Test Redis check is skipped when no backend is configured."""
        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.SKIPPED
        assert result.response_time_ms >= 0

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": 123,  # Non-string backend value
            }
        }
    )
    def test_check_redis_cache_skipped_with_non_string_backend(self) -> None:
        """Test Redis check is skipped when backend is not a string."""
        service = HealthCheckService()
        result = service._check_redis_cache()

        assert isinstance(result, ComponentCheckResult)
        assert result.status == HealthStatus.SKIPPED
        assert result.response_time_ms >= 0
