"""Unit tests for health views (no database, mocked dependencies)."""

from unittest.mock import MagicMock, patch

from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from apps.health.services.health import HealthCheckResult
from apps.health.views import HealthView, get_client_ip


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
        request.META.pop("REMOTE_ADDR", None)

        client_ip = get_client_ip(request)

        assert client_ip == "unknown"

    def test_get_client_ip_with_whitespace_in_x_forwarded_for(self) -> None:
        """Test extracting client IP strips whitespace from X-Forwarded-For."""
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_X_FORWARDED_FOR="  203.0.113.1  , 198.51.100.1")

        client_ip = get_client_ip(request)

        assert client_ip == "203.0.113.1"


class TestHealthView:
    """Unit tests for HealthView (mocked dependencies, no database)."""

    def test_health_view_returns_healthy_status(self) -> None:
        """Test health view returns healthy status when service check passes."""
        factory = APIRequestFactory()
        request = factory.get("/api/health/")

        mock_result = HealthCheckResult(
            http_status=200,
            body={
                "status": "healthy",
                "timestamp": "2024-01-18T12:00:00Z",
                "response_time_ms": 10,
            },
        )

        with patch("apps.health.views.HealthCheckService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.check.return_value = mock_result
            mock_service_class.return_value = mock_service

            view = HealthView()
            response = view.get(request)

            assert response.status_code == 200
            assert response.data["status"] == "healthy"
            assert "timestamp" in response.data
            assert "response_time_ms" in response.data
            mock_service.check.assert_called_once()

    def test_health_view_returns_unhealthy_status(self) -> None:
        """Test health view returns unhealthy status when service check fails."""
        factory = APIRequestFactory()
        request = factory.get("/api/health/")

        mock_result = HealthCheckResult(
            http_status=503,
            body={
                "status": "unhealthy",
                "timestamp": "2024-01-18T12:00:00Z",
                "response_time_ms": 15,
            },
        )

        with patch("apps.health.views.HealthCheckService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.check.return_value = mock_result
            mock_service_class.return_value = mock_service

            view = HealthView()
            response = view.get(request)

            assert response.status_code == 503
            assert response.data["status"] == "unhealthy"

    def test_health_view_logs_client_ip(self) -> None:
        """Test health view logs client IP address."""
        factory = APIRequestFactory()
        request = factory.get("/api/health/", HTTP_X_FORWARDED_FOR="203.0.113.1")

        mock_result = HealthCheckResult(
            http_status=200,
            body={"status": "healthy", "timestamp": "2024-01-18T12:00:00Z", "response_time_ms": 5},
        )

        with patch("apps.health.views.HealthCheckService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.check.return_value = mock_result
            mock_service_class.return_value = mock_service

            with patch("apps.health.views.logger") as mock_logger:
                view = HealthView()
                response = view.get(request)

                assert response.status_code == 200
                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args[1]["msg"]
                assert "203.0.113.1" in call_args

    def test_health_view_permission_classes(self) -> None:
        """Test health view has AllowAny permission."""
        view = HealthView()
        assert view.permission_classes == [AllowAny]

    def test_health_view_authentication_classes(self) -> None:
        """Test health view has no authentication classes."""
        view = HealthView()
        assert view.authentication_classes == []

    def test_health_view_initializes_health_service(self) -> None:
        """Test health view initializes HealthCheckService in constructor."""
        with patch("apps.health.views.HealthCheckService") as mock_service_class:
            view = HealthView()
            assert hasattr(view, "health_service")
            mock_service_class.assert_called_once()
