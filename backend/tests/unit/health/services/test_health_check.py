"""Unit tests for health check service."""

from unittest.mock import Mock, patch

from django.db import OperationalError

from apps.health.services.health_check import HealthCheckResult, HealthCheckService


class TestHealthCheckService:
    """Test HealthCheckService class."""

    @patch("apps.health.services.health_check.connections")
    def test_check_database_success(self, mock_connections):
        """Test database check succeeds."""
        mock_cursor = Mock()
        mock_connections.__getitem__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        service = HealthCheckService()
        result = service._check_database()

        assert result["status"] == "healthy"
        assert "response_time_ms" in result
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @patch("apps.health.services.health_check.connections")
    def test_check_database_failure(self, mock_connections):
        """Test database check handles failure."""
        mock_connections.__getitem__.return_value.cursor.side_effect = OperationalError(
            "Connection failed"
        )

        service = HealthCheckService()
        result = service._check_database()

        assert result["status"] == "unhealthy"
        assert "error" in result

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_healthy_status(self, mock_redis, mock_db):
        """Test check returns healthy status when all checks pass."""
        mock_db.return_value = {"status": "healthy", "response_time_ms": 10}
        mock_redis.return_value = {"status": "healthy", "response_time_ms": 5}

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 200
        assert result.body["overall_status"] == "healthy"
        assert "checks" in result.body
        assert "database" in result.body["checks"]
        assert "redis" in result.body["checks"]

    @patch.object(HealthCheckService, "_check_database")
    @patch.object(HealthCheckService, "_check_redis_cache")
    def test_check_returns_unhealthy_status(self, mock_redis, mock_db):
        """Test check returns unhealthy status when database fails."""
        mock_db.return_value = {"status": "unhealthy", "error": "Connection failed"}
        mock_redis.return_value = {"status": "healthy", "response_time_ms": 5}

        service = HealthCheckService()
        result = service.check()

        assert isinstance(result, HealthCheckResult)
        assert result.http_status == 503
        assert result.body["overall_status"] == "unhealthy"
