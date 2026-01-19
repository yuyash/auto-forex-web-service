"""User login view."""

from logging import Logger, getLogger
from typing import Any

from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middlewares import RateLimiter
from apps.accounts.models import PublicAccountSettings, User, WhitelistedEmail
from apps.accounts.serializers import UserLoginSerializer
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.jwt import JWTService

logger: Logger = getLogger(name=__name__)


@extend_schema_view(
    post=extend_schema(
        summary="User login",
        description="Authenticate user with email and password. Returns JWT token on success. "
        "Rate limited to 5 attempts per 15 minutes per IP address.",
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Login successful",
                response={
                    "type": "object",
                    "properties": {
                        "token": {"type": "string"},
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "email": {"type": "string"},
                                "username": {"type": "string"},
                                "is_staff": {"type": "boolean"},
                                "timezone": {"type": "string"},
                                "language": {"type": "string"},
                            },
                        },
                    },
                },
            ),
            401: OpenApiResponse(description="Invalid credentials"),
            403: OpenApiResponse(description="Account locked or email not whitelisted"),
            429: OpenApiResponse(description="Too many failed login attempts"),
            503: OpenApiResponse(description="Login is disabled"),
        },
        tags=["Authentication"],
    )
)
class UserLoginView(APIView):
    """
    API endpoint for user login.

    POST /api/auth/login
    - Authenticate user with email and password
    - Generate JWT token
    - Implement rate limiting
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = UserLoginSerializer

    def __init__(self, **kwargs: Any) -> None:
        """Initialize view with security event service."""
        super().__init__(**kwargs)
        self.security_events = SecurityEventService()

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0].strip()
        else:
            ip = str(request.META.get("REMOTE_ADDR", ""))
        return ip

    # pylint: disable=too-many-branches,too-many-statements
    def post(self, request: Request) -> Response:
        """Handle user login."""
        system_settings = PublicAccountSettings.get_settings()
        if not system_settings.login_enabled:
            logger.warning(
                "Login attempt blocked - login is disabled",
                extra={"ip_address": self.get_client_ip(request)},
            )
            return Response(
                {"error": "Login is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ip_address = self.get_client_ip(request)
        email = request.data.get("email", "").lower()
        is_admin_user = False

        if email:
            try:
                user_check = User.objects.get(email__iexact=email)
                is_admin_user = user_check.is_staff or user_check.is_superuser
            except User.DoesNotExist:
                pass

        if not is_admin_user:
            is_blocked, block_reason = RateLimiter.is_ip_blocked(ip_address)
            if is_blocked:
                logger.warning(
                    "Login attempt from blocked IP: %s",
                    ip_address,
                    extra={"ip_address": ip_address, "reason": block_reason},
                )
                return Response(
                    {"error": block_reason},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        if email and not is_admin_user:
            try:
                user_check = User.objects.get(email__iexact=email)
                if user_check.is_locked:
                    logger.warning(
                        "Login attempt for locked account %s from %s",
                        email,
                        ip_address,
                        extra={"email": email, "ip_address": ip_address, "user_id": user_check.pk},
                    )
                    return Response(
                        {
                            "error": (
                                "Account is locked due to excessive failed login attempts. "
                                "Please contact support."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except User.DoesNotExist:
                pass

        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            blocked_by_whitelist = False
            credentials_valid = False

            if email and request.data.get("password") and system_settings.email_whitelist_enabled:
                is_whitelisted = WhitelistedEmail.is_email_whitelisted(email)
                if not is_whitelisted:
                    blocked_by_whitelist = True
                    credentials_valid = (
                        authenticate(username=email, password=request.data.get("password"))
                        is not None
                    )
                    logger.warning(
                        "Authentication blocked - email not whitelisted for %s from %s (credentials_valid=%s)",
                        email,
                        ip_address,
                        credentials_valid,
                        extra={
                            "email": email,
                            "ip_address": ip_address,
                            "credentials_valid": credentials_valid,
                            "is_admin": is_admin_user,
                        },
                    )

            if not is_admin_user:
                ip_attempts = (
                    RateLimiter.get_failed_attempts(ip_address)
                    if blocked_by_whitelist
                    else RateLimiter.increment_failed_attempts(ip_address)
                )
            else:
                ip_attempts = 0
                logger.info(
                    "Failed login attempt for admin user %s from %s (rate limiting bypassed)",
                    email,
                    ip_address,
                    extra={"email": email, "ip_address": ip_address, "is_admin": True},
                )

            self.security_events.log_login_failed(
                username=email,
                ip_address=ip_address,
                reason=(
                    "Email not whitelisted (credentials valid)"
                    if blocked_by_whitelist and credentials_valid
                    else (
                        "Email not whitelisted" if blocked_by_whitelist else "Invalid credentials"
                    )
                ),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )

            if not is_admin_user and not blocked_by_whitelist:
                try:
                    user = User.objects.get(email__iexact=email)
                    user.increment_failed_login()

                    if user.failed_login_attempts >= RateLimiter.ACCOUNT_LOCK_THRESHOLD:
                        user.lock_account()
                        logger.error(
                            "Account locked for user %s after %s failed attempts",
                            user.email,
                            user.failed_login_attempts,
                            extra={
                                "user_id": user.pk,
                                "email": user.email,
                                "failed_attempts": user.failed_login_attempts,
                            },
                        )

                        self.security_events.log_account_locked(
                            username=user.username,
                            ip_address=ip_address,
                            failed_attempts=user.failed_login_attempts,
                        )
                except User.DoesNotExist:
                    pass

                if ip_attempts >= RateLimiter.MAX_ATTEMPTS:
                    RateLimiter.block_ip_address(ip_address)
                    logger.error(
                        "IP address %s blocked due to excessive failed login attempts",
                        ip_address,
                        extra={"ip_address": ip_address, "attempts": ip_attempts},
                    )

                self.security_events.log_ip_blocked(
                    ip_address=ip_address,
                    failed_attempts=ip_attempts,
                    duration_seconds=RateLimiter.LOCKOUT_DURATION_MINUTES * 60,
                )

            if blocked_by_whitelist and credentials_valid:
                return Response(
                    {
                        "error": (
                            "This email address is not authorized to login. "
                            "Please contact the administrator."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]

        user.reset_failed_login()
        RateLimiter.reset_failed_attempts(ip_address)

        token = JWTService().generate_token(user)

        self.security_events.log_login_success(
            user=user,
            ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )

        return Response(
            {
                "token": token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "is_staff": user.is_staff,
                    "timezone": user.timezone,
                    "language": user.language,
                },
            },
            status=status.HTTP_200_OK,
        )
