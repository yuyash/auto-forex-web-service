"""Security monitoring middleware and WebSocket authentication for authentication events."""

from datetime import timedelta
from logging import getLogger
from typing import Any, Callable, Dict, Optional, Tuple, cast
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from .models import BlockedIP, User, UserSession
from .jwt_utils import get_user_from_token
from .security_logger import SecurityEventLogger

logger = getLogger(__name__)
UserModel = get_user_model()


def _get_authenticated_user(user: Any) -> User | None:
    """Return authenticated user when available.

    Duck-typed for testability (unit tests use MagicMock and AnonymousUser).
    """

    if user is None:
        return None

    if bool(getattr(user, "is_authenticated", False)):
        return cast(User, user)

    return None


class RateLimiter:
    """
    Rate limiter for authentication endpoints.
    """

    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    ACCOUNT_LOCK_THRESHOLD = 10

    @staticmethod
    def get_cache_key(ip_address: str) -> str:
        return f"login_attempts:{ip_address}"

    @staticmethod
    def get_failed_attempts(ip_address: str) -> int:
        cache_key = RateLimiter.get_cache_key(ip_address)
        attempts = cache.get(cache_key, 0)
        return int(attempts)

    @staticmethod
    def increment_failed_attempts(ip_address: str) -> int:
        cache_key = RateLimiter.get_cache_key(ip_address)
        attempts = RateLimiter.get_failed_attempts(ip_address)
        attempts += 1
        timeout = RateLimiter.LOCKOUT_DURATION_MINUTES * 60
        cache.set(cache_key, attempts, timeout)
        return attempts

    @staticmethod
    def reset_failed_attempts(ip_address: str) -> None:
        cache_key = RateLimiter.get_cache_key(ip_address)
        cache.delete(cache_key)

    @staticmethod
    def is_ip_blocked(ip_address: str) -> Tuple[bool, Optional[str]]:
        attempts = RateLimiter.get_failed_attempts(ip_address)
        if attempts >= RateLimiter.MAX_ATTEMPTS:
            return (
                True,
                f"Too many failed login attempts. "
                f"Try again in {RateLimiter.LOCKOUT_DURATION_MINUTES} minutes.",
            )
        try:
            blocked_ip = BlockedIP.objects.get(ip_address=ip_address)
            if blocked_ip.is_active():
                return True, blocked_ip.reason
        except BlockedIP.DoesNotExist:
            pass
        return False, None

    @staticmethod
    def block_ip_address(ip_address: str, reason: str = "Excessive failed login attempts") -> None:
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip, created = BlockedIP.objects.get_or_create(
            ip_address=ip_address,
            defaults={
                "reason": reason,
                "failed_attempts": RateLimiter.get_failed_attempts(ip_address),
                "blocked_until": blocked_until,
                "is_permanent": False,
            },
        )
        if not created:
            blocked_ip.failed_attempts = RateLimiter.get_failed_attempts(ip_address)
            blocked_ip.blocked_until = blocked_until
            blocked_ip.reason = reason
            blocked_ip.save()

    @staticmethod
    def check_account_lock(user: User) -> Tuple[bool, Optional[str]]:
        if user.is_locked:
            return (
                True,
                "Account is locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        if user.failed_login_attempts >= RateLimiter.ACCOUNT_LOCK_THRESHOLD:
            user.lock_account()
            return (
                True,
                "Account has been locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        return False, None


class SecurityMonitoringMiddleware:
    """
    Middleware for security monitoring and authentication event logging.

    This middleware:
    - Logs all authentication-related requests
    - Tracks IP-based failed login attempts
    - Implements account locking after 10 failed attempts
    - Sends security event signals for logging
    - Blocks IPs after 5 failed attempts
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """
        Initialize the middleware.

        Args:
            get_response: Next middleware or view in the chain
        """
        self.get_response = get_response
        self.security_logger = SecurityEventLogger()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and log security events.

        Args:
            request: HTTP request

        Returns:
            HTTP response
        """
        # Get client IP address
        ip_address = self._get_client_ip(request)

        # Check if IP is blocked before processing
        if self._is_blocked_ip(ip_address):
            # Log blocked IP attempt
            self.security_logger.log_security_event(
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

        # Process the request
        response = self.get_response(request)

        # Track session for authenticated users
        auth_user = self._get_authenticated_user(getattr(request, "user", None))

        if auth_user and response.status_code == 200:
            # Update or create session for authenticated requests
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            self._create_or_update_user_session(
                auth_user,
                ip_address,
                user_agent,
            )

        # Log authentication events based on path and response status
        self._log_authentication_event(request, response, ip_address)

        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address from request.

        Args:
            request: HTTP request

        Returns:
            Client IP address
        """
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
        """
        Check if an IP address is blocked.

        Args:
            ip_address: IP address to check

        Returns:
            True if blocked, False otherwise
        """
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        return is_blocked

    def _log_authentication_event(  # noqa: C901
        self,
        request: HttpRequest,
        response: HttpResponse,
        ip_address: str,
    ) -> None:
        """
        Log authentication-related events.

        Args:
            request: HTTP request
            response: HTTP response
            ip_address: Client IP address
        """
        path = request.path
        method = request.method
        status_code = response.status_code
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Log registration attempts
        if path == "/api/auth/register" and method == "POST":
            if status_code == 201:
                # Successful registration
                self.security_logger.log_security_event(
                    event_type="user_registration",
                    description=f"New user registered from {ip_address}",
                    severity="info",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )
            elif status_code == 503:
                # Registration disabled
                self.security_logger.log_security_event(
                    event_type="registration_blocked",
                    description=(f"Registration attempt blocked " f"(disabled) from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )
            else:
                # Failed registration
                self.security_logger.log_security_event(
                    event_type="registration_failed",
                    description=(f"Failed registration attempt from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )

        # Log login attempts
        elif path == "/api/auth/login" and method == "POST":
            auth_user = self._get_authenticated_user(getattr(request, "user", None))
            if status_code == 200 and auth_user:
                # Successful login - get user from request
                user_email = auth_user.email
                self.security_logger.log_security_event(
                    event_type="login_success",
                    description=(f"User {user_email} logged in from {ip_address}"),
                    severity="info",
                    user=auth_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )

                # Create or update user session
                self._create_or_update_user_session(
                    auth_user,
                    ip_address,
                    user_agent,
                )
            elif status_code == 503:
                # Login disabled
                self.security_logger.log_security_event(
                    event_type="login_blocked",
                    description=(f"Login attempt blocked (disabled) from {ip_address}"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )
            elif status_code == 429:
                # Too many attempts
                self.security_logger.log_security_event(
                    event_type="login_rate_limited",
                    description=(f"Login rate limited for IP {ip_address} " f"(too many attempts)"),
                    severity="warning",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                        "attempts": RateLimiter.get_failed_attempts(ip_address),
                    },
                )
            elif status_code == 403:
                # Account locked
                self.security_logger.log_security_event(
                    event_type="login_account_locked",
                    description=(f"Login attempt for locked account from {ip_address}"),
                    severity="error",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "status_code": status_code,
                    },
                )
            elif status_code == 401:
                # Failed login
                self.security_logger.log_security_event(
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

        # Log logout events
        elif path == "/api/auth/logout" and method == "POST" and status_code == 200:
            auth_user = self._get_authenticated_user(getattr(request, "user", None))
            if not auth_user:
                return
            self.security_logger.log_security_event(
                event_type="logout_success",
                description=(f"User {auth_user.email} logged out from {ip_address}"),
                severity="info",
                user=auth_user,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "status_code": status_code,
                },
            )

    def _create_user_session(
        self,
        user: User,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """
        Create user session record.

        Args:
            user: User instance
            ip_address: Client IP address
            user_agent: User agent string
        """
        # Generate a session key
        session_key = f"{user.pk}_{ip_address}_{timezone.now().timestamp()}"

        # Create new session record
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
        """
        Create or update user session record.

        Args:
            user: User instance
            ip_address: Client IP address
            user_agent: User agent string
        """
        # Try to find an existing active session for this user and IP
        existing_session = UserSession.objects.filter(
            user=user, ip_address=ip_address, is_active=True
        ).first()

        if existing_session:
            # Update last_activity timestamp (auto_now field will update)
            existing_session.save()
            logger.debug(
                "Updated session for user %s from %s",
                user.email,
                ip_address,
            )
        else:
            # Create new session using the _create_user_session method
            self._create_user_session(user, ip_address, user_agent)


class HTTPAccessLoggingMiddleware:
    """
    Middleware for HTTP-level access pattern monitoring.

    This middleware:
    - Logs all HTTP requests with IP, path, method, status, response time
    - Detects SQL injection and path traversal attempts
    - Logs admin endpoint access
    - Monitors suspicious patterns

    Requirements: 35.1, 35.3, 35.4, 35.5
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """
        Initialize the middleware.

        Args:
            get_response: Next middleware or view in the chain
        """
        self.get_response = get_response
        self.security_logger = SecurityEventLogger()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and log HTTP access.

        Args:
            request: HTTP request

        Returns:
            HTTP response
        """
        # Record start time
        start_time = timezone.now()

        # Get client IP address
        ip_address = self._get_client_ip(request)

        # Check for suspicious patterns before processing
        self._detect_suspicious_patterns(request, ip_address)

        # Process the request
        response = self.get_response(request)

        # Calculate response time
        end_time = timezone.now()
        response_time_ms = (end_time - start_time).total_seconds() * 1000

        # Log HTTP access
        self._log_http_access(
            request,
            response,
            ip_address,
            response_time_ms,
        )

        return response

    def _get_authenticated_user(self, user: Any) -> User | None:
        """Return the authenticated User instance when available."""
        return _get_authenticated_user(user)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address from request.

        Args:
            request: HTTP request

        Returns:
            Client IP address
        """
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
        """
        Detect suspicious HTTP patterns.

        Args:
            request: HTTP request
            ip_address: Client IP address
        """
        path = request.path
        query_string = request.META.get("QUERY_STRING", "")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # SQL injection patterns
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

        # Path traversal patterns
        path_traversal_patterns = [
            "../",
            "..\\",
            "%2e%2e/",
            "%2e%2e\\",
            "....//",
            "....\\\\",
        ]

        # Check for SQL injection
        for pattern in sql_patterns:
            if pattern.lower() in path.lower() or pattern.lower() in query_string.lower():
                self.security_logger.log_security_event(
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
                logger.error(
                    "SQL injection attempt detected from %s: %s",
                    ip_address,
                    pattern,
                    extra={
                        "ip_address": ip_address,
                        "path": path,
                        "pattern": pattern,
                    },
                )
                break

        # Check for path traversal
        for pattern in path_traversal_patterns:
            if pattern in path or pattern in query_string:
                self.security_logger.log_security_event(
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
                logger.error(
                    "Path traversal attempt detected from %s: %s",
                    ip_address,
                    pattern,
                    extra={
                        "ip_address": ip_address,
                        "path": path,
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
        """
        Log HTTP access.

        Args:
            request: HTTP request
            response: HTTP response
            ip_address: Client IP address
            response_time_ms: Response time in milliseconds
        """
        path = request.path
        method = request.method
        status_code = response.status_code
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Log admin endpoint access
        if path.startswith("/api/admin/"):
            log_user = self._get_authenticated_user(getattr(request, "user", None))
            is_authenticated = log_user is not None
            is_staff = bool(log_user and log_user.is_staff)

            self.security_logger.log_security_event(
                event_type="admin_endpoint_access",
                description=(f"Admin endpoint access: {method} {path} " f"from {ip_address}"),
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

        # Log all HTTP requests (can be filtered later)
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


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens.

    This middleware:
    - Extracts JWT token from query string (?token=xxx) or headers
    - Validates the token and retrieves the user
    - Adds the user to the WebSocket scope
    - Falls back to AnonymousUser if token is invalid or missing
    """

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> Any:
        """
        Process the WebSocket connection and authenticate the user.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable

        Returns:
            Result of calling the inner application
        """
        # Only process WebSocket connections
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        # Try to get token from query string
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        # If no token in query string, try headers
        if not token:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Authenticate user with token
        if token:
            user = await self.get_user_from_token(token)
            if user:
                scope["user"] = user
                logger.debug(
                    "WebSocket authenticated user %s",
                    user.username,
                )
            else:
                scope["user"] = AnonymousUser()
                logger.warning("Invalid JWT token in WebSocket connection")
        else:
            scope["user"] = AnonymousUser()
            logger.debug("No JWT token provided in WebSocket connection")

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token: str) -> Any:
        """
        Get user from JWT token (database sync to async wrapper).

        Args:
            token: JWT token string

        Returns:
            User instance if token is valid, None otherwise
        """
        return get_user_from_token(token)


def JWTAuthMiddlewareStack(inner: Any) -> Any:  # pylint: disable=invalid-name
    """
    Convenience function to apply JWT authentication middleware.

    Args:
        inner: Inner ASGI application

    Returns:
        Wrapped application with JWT authentication
    """
    return JWTAuthMiddleware(inner)
