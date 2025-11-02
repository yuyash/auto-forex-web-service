"""
Views for user authentication and management.

This module contains views for:
- User registration
- User login
- User logout
"""

import logging

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .jwt_utils import generate_jwt_token, get_user_from_token, refresh_jwt_token
from .models import SystemSettings, UserSession
from .permissions import IsAdminUser
from .rate_limiter import RateLimiter
from .serializers import (
    PublicSystemSettingsSerializer,
    SystemSettingsSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()

logger = logging.getLogger(__name__)


class UserRegistrationView(APIView):
    """
    API endpoint for user registration.

    POST /api/auth/register
    - Register a new user account
    - Send verification email (placeholder)

    Requirements: 1.1, 1.2, 1.3, 1.5
    """

    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def post(self, request: Request) -> Response:
        """
        Handle user registration.

        Args:
            request: HTTP request with email, username, password, password_confirm

        Returns:
            Response with user data or validation errors
        """
        # Check if registration is enabled
        system_settings = SystemSettings.get_settings()
        if not system_settings.registration_enabled:
            logger.warning(
                "Registration attempt blocked - registration is disabled",
                extra={
                    "ip_address": self.get_client_ip(request),
                },
            )
            return Response(
                {"error": "Registration is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Placeholder for future email verification implementation
            # send_verification_email(user)

            return Response(
                {
                    "message": (
                        "User registered successfully. " "Please check your email for verification."
                    ),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request: Request) -> str:
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


class UserLoginView(APIView):
    """
    API endpoint for user login.

    POST /api/auth/login
    - Authenticate user with email and password
    - Generate JWT token
    - Implement rate limiting (5 attempts per 15 minutes)
    - Log failed login attempts

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 34.1, 34.2
    """

    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def get_client_ip(self, request: Request) -> str:
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

    def post(self, request: Request) -> Response:
        """
        Handle user login.

        Args:
            request: HTTP request with email and password

        Returns:
            Response with JWT token or error message
        """
        # Check if login is enabled
        system_settings = SystemSettings.get_settings()
        if not system_settings.login_enabled:
            logger.warning(
                "Login attempt blocked - login is disabled",
                extra={
                    "ip_address": self.get_client_ip(request),
                },
            )
            return Response(
                {"error": "Login is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ip_address = self.get_client_ip(request)

        # Check if IP is blocked
        is_blocked, block_reason = RateLimiter.is_ip_blocked(ip_address)
        if is_blocked:
            logger.warning(
                "Login attempt from blocked IP: %s",
                ip_address,
                extra={
                    "ip_address": ip_address,
                    "reason": block_reason,
                },
            )
            return Response(
                {"error": block_reason},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Check if user exists and is locked before validating credentials
        email = request.data.get("email", "").lower()
        if email:
            try:
                user_check = User.objects.get(email__iexact=email)
                if user_check.is_locked:
                    logger.warning(
                        "Login attempt for locked account %s from %s",
                        email,
                        ip_address,
                        extra={
                            "email": email,
                            "ip_address": ip_address,
                            "user_id": user_check.id,
                        },
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

        # Validate credentials
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            # Increment IP-based failed attempts
            ip_attempts = RateLimiter.increment_failed_attempts(ip_address)

            # Log failed login attempt
            logger.warning(
                "Failed login attempt for %s from %s (IP attempt %s)",
                email,
                ip_address,
                ip_attempts,
                extra={
                    "email": email,
                    "ip_address": ip_address,
                    "ip_attempts": ip_attempts,
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
            )

            # Increment user-level failed attempts if user exists
            try:
                user = User.objects.get(email__iexact=email)
                user.increment_failed_login()

                # Check if account should be locked after increment
                if user.failed_login_attempts >= RateLimiter.ACCOUNT_LOCK_THRESHOLD:
                    user.lock_account()
                    logger.error(
                        "Account locked for user %s after %s failed attempts",
                        user.email,
                        user.failed_login_attempts,
                        extra={
                            "user_id": user.id,
                            "email": user.email,
                            "failed_attempts": user.failed_login_attempts,
                        },
                    )
            except User.DoesNotExist:
                # User doesn't exist, just log the attempt
                pass

            # Block IP if threshold reached
            if ip_attempts >= RateLimiter.MAX_ATTEMPTS:
                RateLimiter.block_ip_address(ip_address)
                logger.error(
                    "IP address %s blocked due to excessive failed login attempts",
                    ip_address,
                    extra={
                        "ip_address": ip_address,
                        "attempts": ip_attempts,
                    },
                )

            # Return generic error message
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get authenticated user
        user = serializer.validated_data["user"]

        # Successful login - reset counters
        user.reset_failed_login()
        RateLimiter.reset_failed_attempts(ip_address)

        # Generate JWT token
        token = generate_jwt_token(user)

        # Log successful login
        logger.info(
            "Successful login for user %s from %s",
            user.email,
            ip_address,
            extra={
                "user_id": user.id,
                "email": user.email,
                "ip_address": ip_address,
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
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


class UserLogoutView(APIView):
    """
    API endpoint for user logout.

    POST /api/auth/logout
    - Invalidate JWT token
    - Close active v20 streams for user
    - Terminate user session

    Requirements: 3.1, 3.2, 3.3, 3.5
    """

    permission_classes = [IsAuthenticated]

    def get_client_ip(self, request: Request) -> str:
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

    def post(self, request: Request) -> Response:
        """
        Handle user logout.

        Args:
            request: HTTP request with Authorization header containing JWT token

        Returns:
            Response with success message or error
        """
        # Get token from Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Invalid authorization header format."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ")[1] if len(auth_header.split(" ")) > 1 else ""
        if not token:
            return Response(
                {"error": "No token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get user from token
        user = get_user_from_token(token)
        if not user:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip_address = self.get_client_ip(request)

        # NOTE: Close active v20 streams for user
        # This will be implemented when the market data streaming module is created
        # For now, we'll log that this should happen
        logger.info(
            "User logout - v20 streams should be closed for user %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
                "ip_address": ip_address,
            },
        )

        # NOTE: Invalidate JWT token
        # JWT tokens are stateless, so we can't truly invalidate them server-side
        # without maintaining a blacklist. For now, we rely on client-side token removal.
        # A token blacklist can be implemented using Redis in the future.
        # The token will naturally expire after JWT_EXPIRATION_DELTA seconds.

        # Terminate user sessions
        active_sessions = UserSession.objects.filter(user=user, is_active=True)
        for session in active_sessions:
            session.terminate()

        logger.info(
            "User %s logged out successfully from %s",
            user.email,
            ip_address,
            extra={
                "user_id": user.id,
                "email": user.email,
                "ip_address": ip_address,
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "sessions_terminated": active_sessions.count(),
            },
        )

        return Response(
            {
                "message": "Logged out successfully.",
                "sessions_terminated": active_sessions.count(),
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    """
    API endpoint for JWT token refresh.

    POST /api/auth/refresh
    - Refresh JWT token if valid
    - Return new token with extended expiration

    Requirements: 2.3, 2.4
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """
        Handle token refresh.

        Args:
            request: HTTP request with Authorization header containing JWT token

        Returns:
            Response with new JWT token or error
        """
        # Get token from Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Invalid authorization header format."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ")[1] if len(auth_header.split(" ")) > 1 else ""
        if not token:
            return Response(
                {"error": "No token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Refresh token
        new_token = refresh_jwt_token(token)
        if not new_token:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get user info for response
        user = get_user_from_token(new_token)
        if not user:
            return Response(
                {"error": "Failed to retrieve user information."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "Token refreshed for user %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return Response(
            {
                "token": new_token,
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


class PublicSystemSettingsView(APIView):
    """
    API endpoint for public system settings (no authentication required).

    GET /api/system/settings/public
    - Return registration_enabled and login_enabled flags
    - Used by frontend to check if features are available

    Requirements: 1.1, 2.1
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:  # pylint: disable=unused-argument
        """
        Get public system settings.

        Args:
            request: HTTP request

        Returns:
            Response with registration_enabled and login_enabled flags
        """
        system_settings = SystemSettings.get_settings()
        serializer = PublicSystemSettingsSerializer(system_settings)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminSystemSettingsView(APIView):
    """
    API endpoint for admin system settings management.

    GET /api/admin/system/settings
    - Retrieve current system settings (admin only)

    PUT /api/admin/system/settings
    - Update system settings (admin only)

    Requirements: 1.1, 2.1, 19.5, 28.5
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request: Request) -> Response:
        """
        Get system settings.

        Args:
            request: HTTP request

        Returns:
            Response with system settings
        """
        system_settings = SystemSettings.get_settings()
        serializer = SystemSettingsSerializer(system_settings)

        if request.user.is_authenticated:
            logger.info(
                "Admin %s retrieved system settings",
                request.user.email,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                },
            )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request) -> Response:
        """
        Update system settings.

        Args:
            request: HTTP request with registration_enabled and/or login_enabled

        Returns:
            Response with updated system settings
        """
        system_settings = SystemSettings.get_settings()
        serializer = SystemSettingsSerializer(system_settings, data=request.data, partial=True)

        if serializer.is_valid():
            # Update the updated_by field
            if request.user.is_authenticated:
                system_settings.updated_by = request.user
            serializer.save()

            if request.user.is_authenticated:
                logger.info(
                    "Admin %s updated system settings: %s",
                    request.user.email,
                    request.data,
                    extra={
                        "user_id": request.user.id,
                        "email": request.user.email,
                        "settings": request.data,
                    },
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
