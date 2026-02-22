"""Security monitoring middleware for authentication event logging."""

from collections.abc import Callable
from logging import Logger, getLogger
from typing import Any, cast

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.accounts.models import User, UserSession
from apps.accounts.services.events import SecurityEventService

from .limiter import RateLimiter

logger: Logger = getLogger(name=__name__)


def _get_authenticated_user(user: Any) -> User | None:
    """Return authenticated user when available."""
    if user is None:
        return None

    if bool(getattr(user, "is_authenticated", False)):
        return cast(User, user)

    return None


class SecurityMonitoringMiddleware:
    """Middleware for security monitoring and authentication event logging."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """Initialize the middleware."""
        self.get_response = get_response
        self.security_events = SecurityEventService()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and log security events."""
        ip_address = self._get_client_ip(request)

        if self._is_blocked_ip(ip_address):
            self.security_events.log_security_event(
                event_type="blocked_ip_attempt",
                description=f"Request from blocked IP: {ip_address}",
                severity="warning",
                ip_address=ip_address,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                details={
                    "path": request.path,
                    "method": request.method,
                },
            )

        response = self.get_response(request)

        auth_user = self._get_authenticated_user(getattr(request, "user", None))

        if auth_user and response.status_code == 200:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            self._create_or_update_user_session(
                auth_user,
                ip_address,
                user_agent,
            )

        self._log_authentication_event(request, response, ip_address)

        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0].strip()
        else:
            ip = str(request.META.get("REMOTE_ADDR", ""))
        return ip

    def _get_authenticated_user(self, user: Any) -> User | None:
        """Return the authenticated User instance when available."""
        return _get_authenticated_user(user)

    def _is_blocked_ip(self, ip_address: str) -> bool:
        """Check if an IP address is blocked."""
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        return is_blocked

    def _log_authentication_event(  # noqa: C901
        self,
        request: HttpRequest,
        response: HttpResponse,
        ip_address: str,
    ) -> None:
        """Log authentication-related events."""
        path = request.path
        method = request.method
        status_code = response.status_code
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        if path in ("/api/auth/register", "/api/accounts/auth/register") and method == "POST":
            if status_code == 201:
                self.security_events.log_security_event(
                    event_type="user_registration",
                    description=f"New user registered from {ip_address}",
                    severity="info",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )
            elif status_code == 503:
                self.security_events.log_security_event(
                    event_type="registration_blocked",
                    description=(f"Registration attempt blocked (disabled) from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )
            else:
                self.security_events.log_security_event(
                    event_type="registration_failed",
                    description=(f"Failed registration attempt from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )

        elif path in ("/api/auth/login", "/api/accounts/auth/login") and method == "POST":
            auth_user = self._get_authenticated_user(getattr(request, "user", None))
            if status_code == 200 and auth_user:
                user_email = auth_user.email
                self.security_events.log_security_event(
                    event_type="login_success",
                    description=(f"User {user_email} logged in from {ip_address}"),
                    severity="info",
                    user=auth_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )

                self._create_or_update_user_session(
                    auth_user,
                    ip_address,
                    user_agent,
                )
            elif status_code == 503:
                self.security_events.log_security_event(
                    event_type="login_blocked",
                    description=(f"Login attempt blocked (disabled) from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )
            elif status_code == 429:
                self.security_events.log_security_event(
                    event_type="login_rate_limited",
                    description=(f"Login rate limited for IP {ip_address} (too many attempts)"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                        "attempts": RateLimiter.get_failed_attempts(ip_address),
                    },
                )
            elif status_code == 403:
                self.security_events.log_security_event(
                    event_type="login_account_locked",
                    description=(f"Login attempt for locked account from {ip_address}"),
                    severity="error",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"status_code": status_code},
                )
            elif status_code == 401:
                self.security_events.log_security_event(
                    event_type="login_failed",
                    description=f"Failed login attempt from {ip_address}",
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                        "attempts": RateLimiter.get_failed_attempts(ip_address),
                    },
                )

        elif (
            path in ("/api/auth/logout", "/api/accounts/auth/logout")
            and method == "POST"
            and status_code == 200
        ):
            auth_user = self._get_authenticated_user(getattr(request, "user", None))
            if not auth_user:
                return
            self.security_events.log_security_event(
                event_type="logout_success",
                description=(f"User {auth_user.email} logged out from {ip_address}"),
                severity="info",
                user=auth_user,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"status_code": status_code},
            )

    def _create_user_session(
        self,
        user: User,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Create user session record."""
        session_key = f"{user.pk}_{ip_address}_{timezone.now().timestamp()}"

        UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "Created session for user %s from %s",
            user.email,
            ip_address,
            extra={
                "user_id": user.pk,
                "email": user.email,
                "ip_address": ip_address,
            },
        )

    def _create_or_update_user_session(
        self,
        user: User,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Create or update user session record."""
        existing_session = UserSession.objects.filter(
            user=user, ip_address=ip_address, is_active=True
        ).first()

        if existing_session:
            existing_session.save()
            logger.debug(
                "Updated session for user %s from %s",
                user.email,
                ip_address,
            )
        else:
            self._create_user_session(user, ip_address, user_agent)
