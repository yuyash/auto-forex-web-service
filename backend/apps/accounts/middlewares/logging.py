"""HTTP access logging middleware for monitoring access patterns."""

from collections.abc import Callable
from logging import Logger, getLogger
from typing import Any
from uuid import uuid4

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.accounts.api_logging import build_request_log_context, safe_request_data
from apps.accounts.models import User
from apps.accounts.request_logging import get_request_id, set_request_id
from apps.accounts.services.events import SecurityEventService

logger: Logger = getLogger(name=__name__)


class HTTPAccessLoggingMiddleware:
    """Middleware for HTTP-level access pattern monitoring."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """Initialize the middleware."""
        self.get_response = get_response
        self.security_events = SecurityEventService()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and log HTTP access."""
        start_time = timezone.now()
        ip_address = self._get_client_ip(request)
        set_request_id(
            request,
            request.META.get("HTTP_X_REQUEST_ID") or str(uuid4()),
        )

        self._detect_suspicious_patterns(request, ip_address)

        try:
            response = self.get_response(request)
        except Exception:
            self._log_unhandled_exception(request, ip_address)
            raise

        end_time = timezone.now()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        response["X-Request-ID"] = get_request_id(request)

        self._log_http_access(
            request,
            response,
            ip_address,
            response_time_ms,
        )
        self._log_http_error(
            request,
            response,
            ip_address,
            response_time_ms,
        )

        return response

    def _get_authenticated_user(self, user: Any) -> User | None:
        """Return the authenticated User instance when available."""
        if user is None:
            return None

        if bool(getattr(user, "is_authenticated", False)):
            return user

        return None

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0].strip()
        else:
            ip = str(request.META.get("REMOTE_ADDR", ""))
        return ip

    def _detect_suspicious_patterns(
        self,
        request: HttpRequest,
        ip_address: str,
    ) -> None:
        """Detect suspicious HTTP patterns."""
        path = request.path
        query_string = request.META.get("QUERY_STRING", "")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        sql_patterns = [
            "' OR '1'='1",
            "' OR 1=1",
            "UNION SELECT",
            "DROP TABLE",
            "INSERT INTO",
            "DELETE FROM",
            "UPDATE SET",
            "--",
            ";--",
            "/*",
            "*/",
            "xp_",
            "sp_",
        ]

        path_traversal_patterns = [
            "../",
            "..\\",
            "%2e%2e/",
            "%2e%2e\\",
            "....//",
            "....\\\\",
        ]

        for pattern in sql_patterns:
            if pattern.lower() in path.lower() or pattern.lower() in query_string.lower():
                self.security_events.log_security_event(
                    event_type="sql_injection_attempt",
                    description=(f"Potential SQL injection attempt from {ip_address}"),
                    severity="critical",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "path": path,
                        "query_string": query_string,
                        "pattern": pattern,
                    },
                )
                break

        for pattern in path_traversal_patterns:
            if pattern in path or pattern in query_string:
                self.security_events.log_security_event(
                    event_type="path_traversal_attempt",
                    description=(f"Potential path traversal attempt from {ip_address}"),
                    severity="critical",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "path": path,
                        "query_string": query_string,
                        "pattern": pattern,
                    },
                )
                break

    def _log_http_access(
        self,
        request: HttpRequest,
        response: HttpResponse,
        ip_address: str,
        response_time_ms: float,
    ) -> None:
        """Log HTTP access."""
        path = request.path
        method = request.method
        status_code = response.status_code
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        if path.startswith("/api/admin/"):
            log_user = self._get_authenticated_user(getattr(request, "user", None))
            is_authenticated = log_user is not None
            is_staff = bool(log_user and log_user.is_staff)

            self.security_events.log_security_event(
                event_type="admin_endpoint_access",
                description=(f"Admin endpoint access: {method} {path} from {ip_address}"),
                severity="info" if is_staff else "warning",
                user=log_user,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "path": path,
                    "method": method,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "is_authenticated": is_authenticated,
                    "is_staff": is_staff,
                },
            )

        user = self._get_authenticated_user(getattr(request, "user", None))
        username = user.username if user else "-"
        content_length = response.get("Content-Length", "-")

        logger.info(
            '%s %s "%s %s HTTP/%s" %s %s %.0fms req_id=%s',
            ip_address,
            username,
            method,
            path,
            request.META.get("SERVER_PROTOCOL", "1.1").split("/")[-1],
            status_code,
            content_length,
            response_time_ms,
            get_request_id(request),
            extra={
                "request_id": get_request_id(request),
                "ip_address": ip_address,
                "username": username,
                "method": method,
                "path": path,
                "status_code": status_code,
                "content_length": content_length,
                "response_time_ms": response_time_ms,
                "user_agent": user_agent,
            },
        )

    def _log_http_error(
        self,
        request: HttpRequest,
        response: HttpResponse,
        ip_address: str,
        response_time_ms: float,
    ) -> None:
        """Log additional request context for API 4xx/5xx responses."""
        if not request.path.startswith("/api/"):
            return
        if response.status_code < 400:
            return

        log_context = build_request_log_context(request)
        log_context.update(
            {
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
                "client_ip": ip_address,
                "request_data": safe_request_data(request),
            }
        )

        if response.status_code >= 500:
            logger.error("API response error", extra=log_context)
        else:
            logger.warning("API response warning", extra=log_context)

    def _log_unhandled_exception(
        self,
        request: HttpRequest,
        ip_address: str,
    ) -> None:
        """Log request context for exceptions raised before a response exists."""
        if not request.path.startswith("/api/"):
            return

        log_context = build_request_log_context(request)
        log_context.update(
            {
                "client_ip": ip_address,
                "request_data": safe_request_data(request),
            }
        )
        logger.exception("Unhandled API exception before response", extra=log_context)
