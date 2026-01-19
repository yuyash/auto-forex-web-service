"""Unit tests for health views."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.health.services.health import HealthCheckResult


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
