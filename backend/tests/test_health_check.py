"""
Unit tests for health check endpoints.

This module tests the health check endpoints for monitoring
backend services including database, Redis, and Celery workers.

Requirements: 6.2, 6.3, 6.4
"""

from unittest.mock import MagicMock, patch

from django.test import Client

import pytest
from rest_framework import status


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


@pytest.mark.django_db
class TestHealthCheckEndpoint:
    """Test suite for health check endpoint."""

    def test_health_check_all_services_healthy(self, client):
        """
        Test health check endpoint when all services are healthy.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor to return healthy status
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_instance = MagicMock()
            mock_monitor.return_value = mock_instance

            # Mock database health check
            mock_instance.check_database_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 5.2,
            }

            # Mock Redis health check
            mock_instance.check_redis_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 2.1,
            }

            # Make request
            response = client.get("/api/health/")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "healthy"
            assert data["database"]["connected"] is True
            assert data["redis"]["status"] == "healthy"
            assert data["redis"]["connected"] is True

    def test_health_check_database_down(self, client):
        """
        Test health check endpoint when database is down.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor to return database error
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_instance = MagicMock()
            mock_monitor.return_value = mock_instance

            # Mock database health check (error)
            mock_instance.check_database_connection.return_value = {
                "status": "error",
                "connected": False,
                "error": "Connection refused",
            }

            # Mock Redis health check (healthy)
            mock_instance.check_redis_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 2.1,
            }

            # Make request
            response = client.get("/api/health/")

            # Assertions
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"]["status"] == "error"
            assert data["database"]["connected"] is False

    def test_health_check_redis_down(self, client):
        """
        Test health check endpoint when Redis is down.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor to return Redis error
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_instance = MagicMock()
            mock_monitor.return_value = mock_instance

            # Mock database health check (healthy)
            mock_instance.check_database_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 5.2,
            }

            # Mock Redis health check (error)
            mock_instance.check_redis_connection.return_value = {
                "status": "error",
                "connected": False,
                "error": "Connection refused",
            }

            # Make request
            response = client.get("/api/health/")

            # Assertions
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["redis"]["status"] == "error"
            assert data["redis"]["connected"] is False

    def test_health_check_response_format(self, client):
        """
        Test health check endpoint response format.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_instance = MagicMock()
            mock_monitor.return_value = mock_instance

            # Mock health checks
            mock_instance.check_database_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 5.2,
            }
            mock_instance.check_redis_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 2.1,
            }

            # Make request
            response = client.get("/api/health/")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Check response structure
            assert "status" in data
            assert "database" in data
            assert "redis" in data

            # Check database structure
            assert "status" in data["database"]
            assert "connected" in data["database"]
            assert "response_time_ms" in data["database"]

            # Check Redis structure
            assert "status" in data["redis"]
            assert "connected" in data["redis"]
            assert "response_time_ms" in data["redis"]

    def test_health_check_exception_handling(self, client):
        """
        Test health check endpoint exception handling.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor to raise exception
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_monitor.side_effect = Exception("Unexpected error")

            # Make request
            response = client.get("/api/health/")

            # Assertions
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data

    def test_health_check_warning_status(self, client):
        """
        Test health check endpoint with warning status.

        Requirements: 6.2, 6.3, 6.4
        """
        # Mock SystemHealthMonitor to return warning status
        with patch("trading.health_views.SystemHealthMonitor") as mock_monitor:
            mock_instance = MagicMock()
            mock_monitor.return_value = mock_instance

            # Mock database health check (warning)
            mock_instance.check_database_connection.return_value = {
                "status": "warning",
                "connected": True,
                "response_time_ms": 150.0,
            }

            # Mock Redis health check (healthy)
            mock_instance.check_redis_connection.return_value = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": 2.1,
            }

            # Make request
            response = client.get("/api/health/")

            # Assertions - warning status should still return 200 OK
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "warning"


@pytest.mark.django_db
class TestSimpleHealthCheck:
    """Test suite for simple health check endpoint."""

    def test_simple_health_check(self, client):
        """
        Test simple health check endpoint.

        Requirements: 6.2, 6.3, 6.4
        """
        # Make request to simple health check
        response = client.get("/api/health/simple/")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
