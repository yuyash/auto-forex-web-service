"""
Views for user authentication and management.

This module contains views for:
- User registration
- User login
- User logout
"""

# pylint: disable=too-many-lines

import logging

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from trading.event_logger import SecurityEventLogger

from .jwt_utils import generate_jwt_token, get_user_from_token, refresh_jwt_token
from .models import SystemSettings, UserSession
from .permissions import IsAdminUser
from .rate_limiter import RateLimiter
from .serializers import (
    OandaAccountSerializer,
    PublicSystemSettingsSerializer,
    SystemSettingsSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()

logger = logging.getLogger(__name__)
security_logger = SecurityEventLogger()


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

            # Log account creation
            security_logger.log_account_created(
                username=user.username,
                email=user.email,
                ip_address=self.get_client_ip(request),
            )

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

            # Log security event
            security_logger.log_login_failed(
                username=email,
                ip_address=ip_address,
                reason="Invalid credentials",
                user_agent=request.META.get("HTTP_USER_AGENT"),
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

                    # Log account locked event
                    security_logger.log_account_locked(
                        username=user.username,
                        ip_address=ip_address,
                        failed_attempts=user.failed_login_attempts,
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

                # Log IP blocked event
                security_logger.log_ip_blocked(
                    ip_address=ip_address,
                    failed_attempts=ip_attempts,
                    duration_seconds=RateLimiter.LOCKOUT_DURATION_MINUTES * 60,
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

        # Log security event
        security_logger.log_login_success(
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

        # Log security event
        security_logger.log_logout(
            user=user,
            ip_address=ip_address,
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


class OandaAccountListCreateView(APIView):
    """
    API endpoint for listing and creating OANDA accounts.

    GET /api/accounts
    - List all OANDA accounts for the authenticated user

    POST /api/accounts
    - Create a new OANDA account for the authenticated user

    Requirements: 4.1, 4.5
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountSerializer

    def get(self, request: Request) -> Response:
        """
        List all OANDA accounts for the authenticated user.

        Args:
            request: HTTP request

        Returns:
            Response with list of OANDA accounts
        """
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        accounts = OandaAccount.objects.filter(user=request.user).order_by("-created_at")
        serializer = self.serializer_class(accounts, many=True)

        logger.info(
            "User %s retrieved %s OANDA accounts",
            request.user.email,
            accounts.count(),
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_count": accounts.count(),
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """
        Create a new OANDA account for the authenticated user.

        Args:
            request: HTTP request with account_id, api_token, api_type, currency

        Returns:
            Response with created OANDA account or validation errors
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.serializer_class(data=request.data, context={"request": request})

        if serializer.is_valid():
            account = serializer.save()

            logger.info(
                "User %s created OANDA account %s (%s)",
                request.user.email,
                account.account_id,
                account.api_type,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OandaAccountDetailView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific OANDA account.

    GET /api/accounts/{id}
    - Retrieve details of a specific OANDA account

    PUT /api/accounts/{id}
    - Update a specific OANDA account

    DELETE /api/accounts/{id}
    - Delete a specific OANDA account

    Requirements: 4.1, 4.5
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountSerializer

    def get_object(
        self, request: Request, account_id: int
    ) -> "OandaAccount | None":  # type: ignore[name-defined]  # noqa: F821
        """
        Get OANDA account by ID, ensuring it belongs to the authenticated user.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            OandaAccount instance or None if not found
        """
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        if not request.user.is_authenticated:
            return None

        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user)
            return account
        except OandaAccount.DoesNotExist:
            return None

    def get(self, request: Request, account_id: int) -> Response:
        """
        Retrieve details of a specific OANDA account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with OANDA account details or error
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(account)

        logger.info(
            "User %s retrieved OANDA account %s",
            request.user.email,
            account.account_id,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account.account_id,
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request, account_id: int) -> Response:
        """
        Update a specific OANDA account.

        Args:
            request: HTTP request with updated account data
            account_id: OANDA account ID

        Returns:
            Response with updated OANDA account or validation errors
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            account, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_account = serializer.save()

            logger.info(
                "User %s updated OANDA account %s",
                request.user.email,
                updated_account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": updated_account.account_id,
                    "updated_fields": list(request.data.keys()),
                },
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, account_id: int) -> Response:
        """
        Delete a specific OANDA account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with success message or error
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        account_id_str = account.account_id
        account.delete()

        logger.info(
            "User %s deleted OANDA account %s",
            request.user.email,
            account_id_str,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account_id_str,
            },
        )

        return Response(
            {"message": "Account deleted successfully."},
            status=status.HTTP_200_OK,
        )


class PositionDifferentiationView(APIView):
    """
    API endpoint for managing position differentiation settings.

    GET /api/accounts/{id}/position-diff
    - Get position differentiation settings for an account

    PUT /api/accounts/{id}/position-diff
    - Update position differentiation settings for an account

    Requirements: 8.1
    """

    permission_classes = [IsAuthenticated]

    def get_object(
        self, request: Request, account_id: int
    ) -> "OandaAccount | None":  # type: ignore[name-defined]  # noqa: F821
        """
        Get OANDA account by ID, ensuring it belongs to the authenticated user.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            OandaAccount instance or None if not found
        """
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        if not request.user.is_authenticated:
            return None

        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user)
            return account
        except OandaAccount.DoesNotExist:
            return None

    def get(self, request: Request, account_id: int) -> Response:
        """
        Get position differentiation settings for an account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with position differentiation settings
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "enable_position_differentiation": account.enable_position_differentiation,
            "position_diff_increment": account.position_diff_increment,
            "position_diff_pattern": account.position_diff_pattern,
        }

        logger.info(
            "User %s retrieved position differentiation settings for account %s",
            request.user.email,
            account.account_id,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account.account_id,
            },
        )

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request: Request, account_id: int) -> Response:
        """
        Update position differentiation settings for an account.

        Args:
            request: HTTP request with updated settings
            account_id: OANDA account ID

        Returns:
            Response with updated settings or validation errors
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate increment amount
        increment = request.data.get("position_diff_increment")
        if increment is not None:
            try:
                increment = int(increment)
                if increment < 1 or increment > 100:
                    return Response(
                        {"error": "Increment amount must be between 1 and 100 units."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Increment amount must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate pattern
        pattern = request.data.get("position_diff_pattern")
        if pattern is not None:
            valid_patterns = ["increment", "decrement", "alternating"]
            if pattern not in valid_patterns:
                return Response(
                    {"error": f"Pattern must be one of: {', '.join(valid_patterns)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Update fields
        if "enable_position_differentiation" in request.data:
            account.enable_position_differentiation = request.data[
                "enable_position_differentiation"
            ]

        if increment is not None:
            account.position_diff_increment = increment

        if pattern is not None:
            account.position_diff_pattern = pattern

        account.save()

        logger.info(
            "User %s updated position differentiation settings for account %s",
            request.user.email,
            account.account_id,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account.account_id,
                "updated_fields": list(request.data.keys()),
            },
        )

        data = {
            "enable_position_differentiation": account.enable_position_differentiation,
            "position_diff_increment": account.position_diff_increment,
            "position_diff_pattern": account.position_diff_pattern,
        }

        return Response(data, status=status.HTTP_200_OK)
