"""Unit tests for health check service."""

from unittest.mock import Mock, patch

from django.db import OperationalError

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
        mock_cursor.execute.assert_called_once_with("SELECT 1")

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
