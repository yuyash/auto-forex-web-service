"""User login view."""

from logging import Logger, getLogger
from typing import Any, cast

from django.contrib.auth import authenticate
from django.http import HttpRequest
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middlewares import RateLimiter
from apps.accounts.middlewares.utils import get_client_ip
from apps.accounts.models import PublicAccountSettings, User, WhitelistedEmail
from apps.accounts.serializers import UserLoginSerializer
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.jwt import JWTService
from apps.accounts.services.sessions import get_or_create_user_session
from apps.accounts.utils.cookies import set_auth_cookies

logger: Logger = getLogger(name=__name__)


class UserLoginView(APIView):
    """
    API endpoint for user login.

    POST /api/accounts/auth/login
    - Authenticate user with email and password
    - Issue access and refresh cookies
    - Implement rate limiting
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    # Uses custom RateLimiter; exempt from DRF throttle.
    throttle_classes: list = []
    serializer_class = UserLoginSerializer

    def __init__(self, **kwargs: Any) -> None:
        """Initialize view with security event service."""
        super().__init__(**kwargs)
        self.security_events = SecurityEventService()

    # pylint: disable=too-many-branches,too-many-statements
    @extend_schema(
        operation_id="auth_login",
        tags=["Accounts"],
        request=UserLoginSerializer,
        responses={
            200: inline_serializer(
                "LoginResponse",
                fields={
                    "authenticated": serializers.BooleanField(),
                    "user": inline_serializer(
                        "LoginUser",
                        fields={
                            "id": serializers.IntegerField(),
                            "email": serializers.EmailField(),
                            "username": serializers.CharField(),
                            "is_staff": serializers.BooleanField(),
                            "timezone": serializers.CharField(),
                            "language": serializers.CharField(),
                        },
                    ),
                },
            ),
            401: inline_serializer("LoginUnauthorized", fields={"error": serializers.CharField()}),
            403: inline_serializer("LoginForbidden", fields={"error": serializers.CharField()}),
            429: inline_serializer("LoginRateLimit", fields={"error": serializers.CharField()}),
            503: inline_serializer(
                "LoginServiceUnavailable", fields={"error": serializers.CharField()}
            ),
        },
    )
    def post(self, request: Request) -> Response:
        """Handle user login."""
        system_settings = PublicAccountSettings.get_settings()
        if not system_settings.login_enabled:
            self.security_events.log_security_event(
                event_type="login_blocked",
                description="Login attempt blocked because login is disabled",
                severity="warning",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                details={"status_code": status.HTTP_503_SERVICE_UNAVAILABLE},
            )
            logger.warning(
                "Login attempt blocked - login is disabled",
                extra={"ip_address": get_client_ip(request)},
            )
            return Response(
                {"error": "Login is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ip_address = get_client_ip(request)
        email = request.data.get("email", "").lower()

        is_blocked, block_reason = RateLimiter.is_ip_blocked(ip_address)
        if is_blocked:
            self.security_events.log_security_event(
                event_type="login_rate_limited",
                description=f"Login rate limited for IP {ip_address}",
                severity="warning",
                ip_address=ip_address,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                details={
                    "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
                    "reason": block_reason,
                    "attempts": RateLimiter.get_failed_attempts(ip_address),
                },
            )
            logger.warning(
                "Login attempt from blocked IP: %s",
                ip_address,
                extra={"ip_address": ip_address, "reason": block_reason},
            )
            return Response(
                {"error": block_reason},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if email:
            try:
                user_check = User.objects.get(email__iexact=email)
                if user_check.is_locked:
                    self.security_events.log_security_event(
                        event_type="login_account_locked",
                        description=f"Locked-account login attempt from {ip_address}",
                        severity="error",
                        user=user_check,
                        ip_address=ip_address,
                        user_agent=request.META.get("HTTP_USER_AGENT", ""),
                        details={"status_code": status.HTTP_403_FORBIDDEN},
                    )
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
                        },
                    )

            ip_attempts = (
                RateLimiter.get_failed_attempts(ip_address)
                if blocked_by_whitelist
                else RateLimiter.increment_failed_attempts(ip_address)
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

            if not blocked_by_whitelist:
                try:
                    user = User.objects.get(email__iexact=email)
                    user.increment_failed_login()

                    if user.failed_login_attempts >= RateLimiter.account_lock_threshold():
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

                if ip_attempts >= RateLimiter.max_attempts():
                    RateLimiter.block_ip_address(ip_address)
                    logger.error(
                        "IP address %s blocked due to excessive failed login attempts",
                        ip_address,
                        extra={"ip_address": ip_address, "attempts": ip_attempts},
                    )
                    self.security_events.log_ip_blocked(
                        ip_address=ip_address,
                        failed_attempts=ip_attempts,
                        duration_seconds=RateLimiter.lockout_seconds(),
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

        jwt_service = JWTService()
        user_session = get_or_create_user_session(
            request,
            user,
            ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        refresh_token = jwt_service.create_refresh_token(
            user,
            session=user_session,
            ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        response = Response(
            {
                "authenticated": True,
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
        get_token(cast(HttpRequest, request._request))
        return set_auth_cookies(response, access_token=token, refresh_token=refresh_token)
