"""Unit tests for API error logging helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.accounts.api_logging import custom_exception_handler, sanitize_for_logging


class TestSanitizeForLogging:
    """Tests for recursive log sanitization."""

    def test_redacts_nested_sensitive_fields(self) -> None:
        payload = {
            "username": "alice",
            "password": "secret",
            "nested": {
                "access_token": "token-value",
            },
        }

        assert sanitize_for_logging(payload) == {
            "username": "alice",
            "password": "[REDACTED]",
            "nested": {
                "access_token": "[REDACTED]",
            },
        }


class TestCustomExceptionHandler:
    """Tests for DRF exception logging."""

    def test_logs_handled_drf_exception_with_context(self) -> None:
        factory = RequestFactory()
        django_request = factory.post(
            "/api/accounts/login/?next=/dashboard",
            data={"username": "alice", "password": "secret"},
            content_type="application/json",
        )
        django_request.user = MagicMock(is_authenticated=False)
        request = Request(django_request)
        view = SimpleNamespace(action="create")

        with patch("apps.accounts.api_logging.logger.warning") as mock_warning:
            response = custom_exception_handler(
                ValidationError({"password": ["This field is required."]}),
                {"request": request, "view": view},
            )

        assert response is not None
        assert response.status_code == 400
        mock_warning.assert_called_once()
        extra = mock_warning.call_args.kwargs["extra"]
        assert extra["status_code"] == 400
        assert extra["path"] == "/api/accounts/login/"
        assert extra["query_params"] == {"next": "/dashboard"}
        assert extra["request_data"] == {
            "username": "alice",
            "password": "[REDACTED]",
        }

    def test_logs_unhandled_exception_with_context(self) -> None:
        factory = RequestFactory()
        django_request = factory.get("/api/trading/tasks/backtest/")
        django_request.user = MagicMock(is_authenticated=False)
        request = Request(django_request)

        with patch("apps.accounts.api_logging.logger.exception") as mock_exception:
            response = custom_exception_handler(
                RuntimeError("boom"),
                {"request": request, "view": SimpleNamespace(action="list")},
            )

        assert response is None
        mock_exception.assert_called_once()
        extra = mock_exception.call_args.kwargs["extra"]
        assert extra["exception_class"] == "RuntimeError"
        assert extra["path"] == "/api/trading/tasks/backtest/"
