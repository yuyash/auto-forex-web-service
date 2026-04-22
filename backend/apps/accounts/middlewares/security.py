"""Security monitoring middleware for coarse request/session events."""

from collections.abc import Callable
from logging import Logger, getLogger

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from apps.accounts.models import User
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.sessions import get_or_create_user_session

from .limiter import RateLimiter
from .utils import get_authenticated_user, get_client_ip

logger: Logger = getLogger(name=__name__)

# Cache session existence checks to avoid a DB query on every request.
_SESSION_CHECK_CACHE_TTL = 300  # 5 minutes


class SecurityMonitoringMiddleware:
    """Middleware for coarse request/session events.

    Fine-grained authentication lifecycle events are emitted from the
    corresponding views/services so they are not coupled to URL paths here.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """Initialize the middleware."""
        self.get_response = get_response
        self.security_events = SecurityEventService()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and log security events."""
        ip_address = get_client_ip(request)

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

        auth_user = get_authenticated_user(getattr(request, "user", None))

        if auth_user and response.status_code == 200:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            self._create_or_update_user_session(
                request,
                auth_user,
                ip_address,
                user_agent,
            )

        return response

    def _is_blocked_ip(self, ip_address: str) -> bool:
        """Check if an IP address is blocked."""
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        return is_blocked

    def _create_or_update_user_session(
        self,
        request: HttpRequest,
        user: User,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Create a user session record if one does not already exist.

        Uses a short-lived cache key to avoid hitting the database on every
        single authenticated request.
        """
        session = getattr(request, "session", None)
        session_key = getattr(session, "session_key", None)
        cache_key = f"session_exists:{user.pk}:{session_key or ip_address}"
        if cache.get(cache_key):
            return

        get_or_create_user_session(
            request,
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        cache.set(cache_key, True, timeout=_SESSION_CHECK_CACHE_TTL)
