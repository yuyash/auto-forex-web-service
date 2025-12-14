"""
Views for user authentication and management.

This module contains views for:
- User registration
- User login
- User logout
"""

import logging

from django.conf import settings

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import (
    PublicAccountSettings,
    User,
    UserNotification,
    UserSession,
    UserSettings,
    WhitelistedEmail,
)
from apps.accounts.services.jwt import JWTService
from apps.accounts.permissions import IsAdminUser
from apps.accounts.middleware import RateLimiter
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.email import AccountEmailService
from apps.accounts.serializers import (
    PublicAccountSettingsSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSettingsSerializer,
    WhitelistedEmailSerializer,
)

logger = logging.getLogger(__name__)
security_events = SecurityEventService()


class UserRegistrationView(APIView):
    """
    API endpoint for user registration.

    POST /api/auth/register
    - Register a new user account
    - Send verification email
    """

    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def build_verification_url(self, request: Request, token: str) -> str:
        """
        Build email verification URL.

        Args:
            request: HTTP request
            token: Verification token

        Returns:
            Full verification URL
        """
        # Use FRONTEND_URL from settings if available, otherwise build from request
        if hasattr(settings, "FRONTEND_URL") and settings.FRONTEND_URL:
            base_url = settings.FRONTEND_URL
        else:
            # Fallback to building from request
            scheme = "https" if request.is_secure() else "http"
            host = request.get_host()
            base_url = f"{scheme}://{host}"

        return f"{base_url}/verify-email?token={token}"

    def post(self, request: Request) -> Response:
        """
        Handle user registration.

        Args:
            request: HTTP request with email, username, password, password_confirm

        Returns:
            Response with user data or validation errors
        """
        # Check if registration is enabled
        system_settings = PublicAccountSettings.get_settings()
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
            security_events.log_account_created(
                username=user.username,
                email=user.email,
                ip_address=self.get_client_ip(request),
            )

            # Generate verification token and send email
            token = user.generate_verification_token()
            verification_url = self.build_verification_url(request, token)

            email_service = AccountEmailService()
            email_sent = email_service.send_verification_email(
                user,
                verification_url,
                sender=self.__class__,
            )

            if not email_sent:
                logger.warning(
                    "Failed to send verification email to %s",
                    user.email,
                    extra={
                        "user_id": user.id,
                        "email": user.email,
                    },
                )

            return Response(
                {
                    "message": (
                        "User registered successfully. "
                        "Please check your email for verification link."
                    ),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email_verified": user.email_verified,
                    },
                    "email_sent": email_sent,
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


class EmailVerificationView(APIView):
    """
    API endpoint for email verification.

    POST /api/auth/verify-email
    - Verify user email with token
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """
        Verify user email with token.

        Args:
            request: HTTP request with token

        Returns:
            Response with success or error message
        """
        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find user with this token
        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify email
        if user.verify_email(token):
            AccountEmailService().send_welcome_message(
                user,
                sender=self.__class__,
            )

            logger.info(
                "Email verified for user %s",
                user.email,
                extra={
                    "user_id": user.pk,
                    "email": user.email,
                },
            )

            return Response(
                {
                    "message": "Email verified successfully. You can now log in.",
                    "user": {
                        "id": user.pk,
                        "email": user.email,
                        "username": user.username,
                        "email_verified": user.email_verified,
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "Invalid or expired verification token."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ResendVerificationEmailView(APIView):
    """
    API endpoint for resending verification email.

    POST /api/auth/resend-verification
    - Resend verification email to user
    """

    permission_classes = [AllowAny]

    def build_verification_url(self, request: Request, token: str) -> str:
        """
        Build email verification URL.

        Args:
            request: HTTP request
            token: Verification token

        Returns:
            Full verification URL
        """
        # Use FRONTEND_URL from settings if available, otherwise build from request
        if hasattr(settings, "FRONTEND_URL") and settings.FRONTEND_URL:
            base_url = settings.FRONTEND_URL
        else:
            # Fallback to building from request
            scheme = "https" if request.is_secure() else "http"
            host = request.get_host()
            base_url = f"{scheme}://{host}"

        return f"{base_url}/verify-email?token={token}"

    def post(self, request: Request) -> Response:
        """
        Resend verification email.

        Args:
            request: HTTP request with email

        Returns:
            Response with success or error message
        """
        email = request.data.get("email", "").lower()

        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find user
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Don't reveal if email exists or not
            return Response(
                {
                    "message": (
                        "If an account with this email exists and is not verified, "
                        "a verification email will be sent."
                    )
                },
                status=status.HTTP_200_OK,
            )

        # Check if already verified
        if user.email_verified:
            return Response(
                {"error": "Email is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate new token and send email via signal
        token = user.generate_verification_token()
        verification_url = self.build_verification_url(request, token)

        email_service = AccountEmailService()
        email_sent = email_service.send_verification_email(
            user,
            verification_url,
            sender=self.__class__,
        )

        if email_sent:
            logger.info(
                "Verification email resent to %s",
                user.email,
                extra={
                    "user_id": user.pk,
                    "email": user.email,
                },
            )

        return Response(
            {
                "message": "Verification email sent. Please check your inbox.",
                "email_sent": email_sent,
            },
            status=status.HTTP_200_OK,
        )


class UserLoginView(APIView):
    """
    API endpoint for user login.

    POST /api/auth/login
    - Authenticate user with email and password
    - Generate JWT token
    - Implement rate limiting (5 attempts per 15 minutes)
    - Log failed login attempts
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

    # pylint: disable=too-many-branches,too-many-statements
    def post(self, request: Request) -> Response:
        """
        Handle user login.

        Args:
            request: HTTP request with email and password

        Returns:
            Response with JWT token or error message
        """
        # Check if login is enabled
        system_settings = PublicAccountSettings.get_settings()
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

        # Check if user is admin FIRST (before IP blocking check)
        email = request.data.get("email", "").lower()
        is_admin_user = False
        if email:
            try:
                user_check = User.objects.get(email__iexact=email)
                # Admin/staff users bypass rate limiting and account locking
                is_admin_user = user_check.is_staff or user_check.is_superuser
            except User.DoesNotExist:
                pass

        # Check if IP is blocked (skip for admin users)
        if not is_admin_user:
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

        # Check if user account is locked (already have user_check from above)
        if email and not is_admin_user:
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
                            "user_id": user_check.pk,
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
            # Admin users bypass rate limiting but still log attempts
            if not is_admin_user:
                # Increment IP-based failed attempts
                ip_attempts = RateLimiter.increment_failed_attempts(ip_address)
            else:
                ip_attempts = 0
                logger.info(
                    "Failed login attempt for admin user %s from %s (rate limiting bypassed)",
                    email,
                    ip_address,
                    extra={
                        "email": email,
                        "ip_address": ip_address,
                        "is_admin": True,
                    },
                )

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
                    "is_admin": is_admin_user,
                },
            )

            # Log security event
            security_events.log_login_failed(
                username=email,
                ip_address=ip_address,
                reason="Invalid credentials",
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )

            # Increment user-level failed attempts if user exists (skip for admin users)
            if not is_admin_user:
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
                                "user_id": user.pk,
                                "email": user.email,
                                "failed_attempts": user.failed_login_attempts,
                            },
                        )

                        # Log account locked event
                        security_events.log_account_locked(
                            username=user.username,
                            ip_address=ip_address,
                            failed_attempts=user.failed_login_attempts,
                        )
                except User.DoesNotExist:
                    # User doesn't exist, just log the attempt
                    pass

                # Block IP if threshold reached (only for non-admin users)
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
                security_events.log_ip_blocked(
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
        token = JWTService().generate_token(user)

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
        security_events.log_login_success(
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
        user = JWTService().get_user_from_token(token)
        if not user:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip_address = self.get_client_ip(request)

        # Invalidate JWT token
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
        security_events.log_logout(
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
        new_token = JWTService().refresh_token(token)
        if not new_token:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get user info for response
        user = JWTService().get_user_from_token(new_token)
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


class UserSettingsView(APIView):
    """
    API endpoint for managing user settings.

    GET /api/settings
    - Get user settings including timezone, language, and strategy defaults

    PUT /api/settings
    - Update user settings
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        Get user settings.

        Args:
            request: HTTP request

        Returns:
            Response with user profile and settings
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get or create user settings
        user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

        # Serialize user profile
        user_serializer = UserProfileSerializer(request.user)

        # Serialize user settings
        settings_serializer = UserSettingsSerializer(user_settings)

        # Combine both into a single response
        response_data = {
            "user": user_serializer.data,
            "settings": settings_serializer.data,
        }

        logger.info(
            "User %s retrieved settings",
            request.user.email,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
            },
        )

        return Response(response_data, status=status.HTTP_200_OK)

    def put(self, request: Request) -> Response:
        """
        Update user settings.

        Args:
            request: HTTP request with updated settings

        Returns:
            Response with updated settings or validation errors
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get or create user settings
        user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

        # Separate user profile fields from settings fields
        user_data = {}
        settings_data = {}

        # User profile fields
        user_fields = ["timezone", "language", "first_name", "last_name", "username"]
        for field in user_fields:
            if field in request.data:
                user_data[field] = request.data[field]

        # Settings fields
        settings_fields = [
            "notification_enabled",
            "notification_email",
            "notification_browser",
            "settings_json",
        ]
        for field in settings_fields:
            if field in request.data:
                settings_data[field] = request.data[field]

        # Validate and update user profile
        user_serializer = UserProfileSerializer(request.user, data=user_data, partial=True)
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Validate and update settings
        settings_serializer = UserSettingsSerializer(
            user_settings, data=settings_data, partial=True
        )
        if not settings_serializer.is_valid():
            return Response(settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Save both if validation passed
        user_serializer.save()
        settings_serializer.save()

        # Combine both into a single response
        response_data = {
            "user": user_serializer.data,
            "settings": settings_serializer.data,
        }

        logger.info(
            "User %s updated settings: %s",
            request.user.email,
            list(request.data.keys()),
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "updated_fields": list(request.data.keys()),
            },
        )

        return Response(response_data, status=status.HTTP_200_OK)


class WhitelistedEmailListCreateView(APIView):
    """
    API endpoint for listing and creating whitelisted emails.

    GET /api/admin/whitelist/emails
    - List all whitelisted emails (admin only)

    POST /api/admin/whitelist/emails
    - Create a new whitelisted email entry (admin only)
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request: Request) -> Response:
        """
        List all whitelisted emails.

        Args:
            request: HTTP request

        Returns:
            Response with list of whitelisted emails
        """
        # Get query parameters for filtering
        is_active = request.query_params.get("is_active")

        queryset = WhitelistedEmail.objects.all().order_by("email_pattern")

        # Filter by active status if provided
        if is_active is not None:
            is_active_bool = is_active.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(is_active=is_active_bool)

        serializer = WhitelistedEmailSerializer(queryset, many=True)

        if request.user.is_authenticated:
            logger.info(
                "Admin %s retrieved %s whitelisted emails",
                request.user.email,
                queryset.count(),
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "count": queryset.count(),
                },
            )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        """
        Create a new whitelisted email entry.

        Args:
            request: HTTP request with email_pattern, description, is_active

        Returns:
            Response with created entry or validation errors
        """
        serializer = WhitelistedEmailSerializer(data=request.data)

        if serializer.is_valid():
            # Save with created_by field
            whitelist_entry = serializer.save(created_by=request.user)

            if request.user.is_authenticated:
                logger.info(
                    "Admin %s created whitelisted email: %s",
                    request.user.email,
                    whitelist_entry.email_pattern,
                    extra={
                        "user_id": request.user.id,
                        "email": request.user.email,
                        "email_pattern": whitelist_entry.email_pattern,
                    },
                )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WhitelistedEmailDetailView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific whitelisted email.

    GET /api/admin/whitelist/emails/{id}
    - Retrieve details of a specific whitelisted email (admin only)

    PUT /api/admin/whitelist/emails/{id}
    - Update a specific whitelisted email (admin only)

    DELETE /api/admin/whitelist/emails/{id}
    - Delete a specific whitelisted email (admin only)
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_object(self, whitelist_id: int) -> "WhitelistedEmail | None":  # noqa: F821
        """
        Get whitelisted email by ID.

        Args:
            whitelist_id: Whitelisted email ID

        Returns:
            WhitelistedEmail instance or None if not found
        """
        try:
            return WhitelistedEmail.objects.get(id=whitelist_id)
        except WhitelistedEmail.DoesNotExist:
            return None

    def get(self, request: Request, whitelist_id: int) -> Response:
        """
        Retrieve details of a specific whitelisted email.

        Args:
            request: HTTP request
            whitelist_id: Whitelisted email ID

        Returns:
            Response with whitelisted email details or error
        """
        whitelist_entry = self.get_object(whitelist_id)
        if whitelist_entry is None:
            return Response(
                {"error": "Whitelisted email not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WhitelistedEmailSerializer(whitelist_entry)

        if request.user.is_authenticated:
            logger.info(
                "Admin %s retrieved whitelisted email: %s",
                request.user.email,
                whitelist_entry.email_pattern,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "email_pattern": whitelist_entry.email_pattern,
                },
            )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request, whitelist_id: int) -> Response:
        """
        Update a specific whitelisted email.

        Args:
            request: HTTP request with updated data
            whitelist_id: Whitelisted email ID

        Returns:
            Response with updated entry or validation errors
        """
        whitelist_entry = self.get_object(whitelist_id)
        if whitelist_entry is None:
            return Response(
                {"error": "Whitelisted email not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WhitelistedEmailSerializer(whitelist_entry, data=request.data, partial=True)

        if serializer.is_valid():
            updated_entry = serializer.save()

            if request.user.is_authenticated:
                logger.info(
                    "Admin %s updated whitelisted email: %s",
                    request.user.email,
                    updated_entry.email_pattern,
                    extra={
                        "user_id": request.user.id,
                        "email": request.user.email,
                        "email_pattern": updated_entry.email_pattern,
                        "updated_fields": list(request.data.keys()),
                    },
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, whitelist_id: int) -> Response:
        """
        Delete a specific whitelisted email.

        Args:
            request: HTTP request
            whitelist_id: Whitelisted email ID

        Returns:
            Response with success message or error
        """
        whitelist_entry = self.get_object(whitelist_id)
        if whitelist_entry is None:
            return Response(
                {"error": "Whitelisted email not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        email_pattern = whitelist_entry.email_pattern
        whitelist_entry.delete()

        if request.user.is_authenticated:
            logger.info(
                "Admin %s deleted whitelisted email: %s",
                request.user.email,
                email_pattern,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "email_pattern": email_pattern,
                },
            )

        return Response(
            {"message": "Whitelisted email deleted successfully."},
            status=status.HTTP_200_OK,
        )


class PublicAccountSettingsView(APIView):
    """
    API endpoint for public account settings (no authentication required).

    GET /api/accounts/settings/public
    - Return registration_enabled and login_enabled flags
    - Used by frontend to check if features are available
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:  # pylint: disable=unused-argument
        """
        Get public account settings.

        Args:
            request: HTTP request

        Returns:
            Response with registration_enabled and login_enabled flags
        """
        account_settings = PublicAccountSettings.get_settings()
        serializer = PublicAccountSettingsSerializer(account_settings)

        return Response(serializer.data, status=status.HTTP_200_OK)


class UserNotificationListView(APIView):
    """List notifications for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            limit_raw = request.query_params.get("limit")
            limit = 50
            if limit_raw:
                try:
                    limit = max(1, min(int(limit_raw), 200))
                except ValueError:
                    limit = 50

            unread_only = request.query_params.get("unread_only")
            unread_only_bool = str(unread_only).lower() in {"1", "true", "yes"}

            queryset = UserNotification.objects.filter(user_id=user_id).order_by("-timestamp")
            if unread_only_bool:
                queryset = queryset.filter(is_read=False)

            notifications = list(queryset[:limit])

            data = [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "severity": n.severity,
                    "timestamp": n.timestamp.isoformat(),
                    "read": n.is_read,
                    "notification_type": n.notification_type,
                    "extra_data": n.extra_data,
                }
                for n in notifications
            ]
            return Response(data, status=status.HTTP_200_OK)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to list user notifications: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to retrieve notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserNotificationMarkReadView(APIView):
    """Mark a single notification as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, notification_id: int) -> Response:
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            notification = UserNotification.objects.get(id=notification_id, user_id=user_id)
            if not notification.is_read:
                notification.is_read = True
                notification.save(update_fields=["is_read"])

            return Response(
                {"message": "Notification marked as read"},
                status=status.HTTP_200_OK,
            )

        except UserNotification.DoesNotExist:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to mark user notification as read: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to mark notification as read"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserNotificationMarkAllReadView(APIView):
    """Mark all unread notifications as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            count = UserNotification.objects.filter(user_id=user_id, is_read=False).update(
                is_read=True
            )

            return Response(
                {"message": f"{count} notifications marked as read", "count": count},
                status=status.HTTP_200_OK,
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to mark all user notifications as read: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to mark all notifications as read"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
