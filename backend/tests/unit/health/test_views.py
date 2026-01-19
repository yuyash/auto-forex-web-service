"""Unit tests for health views."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.health.services.health import HealthCheckResult
from apps.health.views import get_client_ip


@pytest.mark.django_db
class TestHealthCheckView:
    """Test health check view."""

    def test_health_check_returns_200(self):
        """Test health check returns 200 OK."""
        client = APIClient()
        url = reverse("health:health_check")

        with patch("apps.health.views.HealthCheckService.check") as mock_check:
            mock_check.return_value = HealthCheckResult(
                http_status=200,
                body={
                    "status": "healthy",
                    "timestamp": "2024-01-18T12:00:00Z",
                    "response_time_ms": 10,
                },
            )
            response = client.get(url)

            assert response.status_code == status.HTTP_200_OK
            assert "status" in response.data
            assert response.data["status"] == "healthy"

    @patch("apps.health.views.HealthCheckService.check")
    def test_health_check_with_healthy_database(self, mock_check):
        """Test health check with healthy database."""
        mock_check.return_value = HealthCheckResult(
            http_status=200,
            body={
                "status": "healthy",
                "timestamp": "2024-01-18T12:00:00Z",
                "response_time_ms": 10,
            },
        )

        client = APIClient()
        url = reverse("health:health_check")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert "timestamp" in response.data
        assert "response_time_ms" in response.data
        mock_check.assert_called_once()

    @patch("apps.health.views.HealthCheckService.check")
    def test_health_check_handles_database_failure(self, mock_check):
        """Test health check handles database failure."""
        mock_check.return_value = HealthCheckResult(
            http_status=503,
            body={
                "status": "unhealthy",
                "timestamp": "2024-01-18T12:00:00Z",
                "response_time_ms": 10,
            },
        )

        client = APIClient()
        url = reverse("health:health_check")
        response = client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"


class TestGetClientIP:
    """Test get_client_ip helper function."""

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1")

        client_ip = get_client_ip(request)

        assert client_ip == "203.0.113.1"

    def test_get_client_ip_with_single_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For with single IP."""
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_X_FORWARDED_FOR="203.0.113.1")

        client_ip = get_client_ip(request)

        assert client_ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR when no X-Forwarded-For."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        client_ip = get_client_ip(request)

        assert client_ip == "192.168.1.1"

    def test_get_client_ip_with_no_remote_addr(self) -> None:
        """Test extracting client IP returns 'unknown' when no IP available."""
        factory = APIRequestFactory()
        request = factory.get("/")
        # Remove REMOTE_ADDR if it exists
        request.META.pop("REMOTE_ADDR", None)

        client_ip = get_client_ip(request)

        assert client_ip == "unknown"

    def test_get_client_ip_with_whitespace_in_x_forwarded_for(self) -> None:
        """Test extracting client IP strips whitespace from X-Forwarded-For."""
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_X_FORWARDED_FOR="  203.0.113.1  , 198.51.100.1")

        client_ip = get_client_ip(request)

        assert client_ip == "203.0.113.1"
