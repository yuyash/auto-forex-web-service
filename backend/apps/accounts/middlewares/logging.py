"""HTTP access logging middleware for monitoring access patterns."""

from collections.abc import Callable
from logging import Logger, getLogger
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.accounts.models import User
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

        self._detect_suspicious_patterns(request, ip_address)

        response = self.get_response(request)

        end_time = timezone.now()
        response_time_ms = (end_time - start_time).total_seconds() * 1000

        self._log_http_access(
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

        logger.debug(
            "%s %s %s %s %.2fms",
            ip_address,
            method,
            path,
            status_code,
            response_time_ms,
            extra={
                "ip_address": ip_address,
                "method": method,
                "path": path,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "user_agent": user_agent,
            },
        )
