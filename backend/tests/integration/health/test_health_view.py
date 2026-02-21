"""Integration tests for HealthView endpoint (real database, HTTP layer)."""

from unittest.mock import MagicMock, patch

import pytest
from django.db.utils import OperationalError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestHealthViewIntegration:
    """Integration test suite for HealthView endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test client for each test."""
        self.client = APIClient()
        self.url = reverse("health:health_check")

    def test_health_check_success_with_real_database(self) -> None:
        """Test health check returns 200 when all systems are healthy (real DB)."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert "status" in response.data
        assert response.data["status"] == "healthy"
        assert "timestamp" in response.data
        assert "response_time_ms" in response.data
        assert isinstance(response.data["response_time_ms"], int)
        assert response.data["response_time_ms"] >= 0

    def test_health_check_response_structure(self) -> None:
        """Test health check response has correct structure."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        expected_keys = {"status", "timestamp", "response_time_ms"}
        assert set(response.data.keys()) == expected_keys

    def test_health_check_timestamp_format(self) -> None:
        """Test health check timestamp is in ISO 8601 format."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        timestamp = response.data["timestamp"]
        assert isinstance(timestamp, str)
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp or "-" in timestamp[-6:]

    def test_health_check_no_authentication_required(self) -> None:
        """Test health check endpoint does not require authentication."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"

    def test_health_check_database_failure(self) -> None:
        """Test health check returns 503 when database is unavailable."""
        with patch("apps.health.services.health.connections") as mock_connections:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = OperationalError("Database connection failed")
            mock_connections.__getitem__.return_value.cursor.return_value.__enter__.return_value = (
                mock_cursor
            )

            response = self.client.get(self.url)

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data["status"] == "unhealthy"
            assert "timestamp" in response.data
            assert "response_time_ms" in response.data

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://localhost:6379/1",
            }
        }
    )
    def test_health_check_redis_failure(self) -> None:
        """Test health check returns 503 when Redis is unavailable."""
        with patch("apps.health.services.health.caches") as mock_caches:
            mock_cache = MagicMock()
            mock_cache.set.side_effect = Exception("Redis connection failed")
            mock_caches.__getitem__.return_value = mock_cache

            response = self.client.get(self.url)

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data["status"] == "unhealthy"

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
            }
        }
    )
    def test_health_check_with_dummy_cache(self) -> None:
        """Test health check succeeds with DummyCache (skips Redis check)."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"

    def test_health_check_response_time_reasonable(self) -> None:
        """Test health check response time is reasonable (< 1000ms)."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["response_time_ms"] < 1000

    def test_health_check_multiple_requests(self) -> None:
        """Test health check can handle multiple consecutive requests."""
        for _ in range(5):
            response = self.client.get(self.url)
            assert response.status_code == status.HTTP_200_OK
            assert response.data["status"] == "healthy"

    def test_health_check_with_x_forwarded_for_header(self) -> None:
        """Test health check correctly handles X-Forwarded-For header."""
        response = self.client.get(
            self.url,
            HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_health_check_method_not_allowed(self) -> None:
        """Test health check only accepts GET requests."""
        response = self.client.post(self.url, data={})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        response = self.client.put(self.url, data={})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_health_check_content_type(self) -> None:
        """Test health check returns JSON content type."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response["Content-Type"]

    def test_health_check_concurrent_requests(self) -> None:
        """Test health check can handle concurrent requests safely."""
        import concurrent.futures

        def make_request() -> int:
            response = self.client.get(self.url)
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        assert all(result == status.HTTP_200_OK for result in results)
        assert len(results) == 10
