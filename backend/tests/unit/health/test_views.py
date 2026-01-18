"""Unit tests for health views."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.health.services.health_check import HealthCheckResult


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
                body={"overall_status": "healthy", "checks": {}},
            )
            response = client.get(url)

            assert response.status_code == status.HTTP_200_OK
            assert "overall_status" in response.data

    @patch("apps.health.views.HealthCheckService.check")
    def test_health_check_with_healthy_database(self, mock_check):
        """Test health check with healthy database."""
        mock_check.return_value = HealthCheckResult(
            http_status=200,
            body={
                "overall_status": "healthy",
                "checks": {
                    "database": {"status": "healthy"},
                    "redis": {"status": "healthy"},
                },
            },
        )

        client = APIClient()
        url = reverse("health:health_check")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["overall_status"] == "healthy"
        mock_check.assert_called_once()

    @patch("apps.health.views.HealthCheckService.check")
    def test_health_check_handles_database_failure(self, mock_check):
        """Test health check handles database failure."""
        mock_check.return_value = HealthCheckResult(
            http_status=503,
            body={
                "overall_status": "unhealthy",
                "checks": {
                    "database": {"status": "unhealthy", "error": "Connection failed"},
                    "redis": {"status": "healthy"},
                },
            },
        )

        client = APIClient()
        url = reverse("health:health_check")
        response = client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["overall_status"] == "unhealthy"
