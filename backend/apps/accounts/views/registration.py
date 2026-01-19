"""User registration view."""

from logging import Logger, getLogger
from typing import Any

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PublicAccountSettings
from apps.accounts.serializers import UserRegistrationSerializer
from apps.accounts.services.email import AccountEmailService
from apps.accounts.services.events import SecurityEventService

logger: Logger = getLogger(name=__name__)


@extend_schema_view(
    post=extend_schema(
        summary="Register new user",
        description="Register a new user account and send email verification link.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                description="User registered successfully",
                response={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "email": {"type": "string"},
                                "username": {"type": "string"},
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                                "email_verified": {"type": "boolean"},
                            },
                        },
                        "email_sent": {"type": "boolean"},
                    },
                },
            ),
            400: OpenApiResponse(description="Validation error"),
            503: OpenApiResponse(description="Registration is disabled"),
        },
        tags=["Authentication"],
    )
)
class UserRegistrationView(APIView):
    """
    API endpoint for user registration.

    POST /api/auth/register
    - Register a new user account
    - Send verification email
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = UserRegistrationSerializer

    def __init__(self, **kwargs: Any) -> None:
        """Initialize view with security event service."""
        super().__init__(**kwargs)
        self.security_events = SecurityEventService()

    def build_verification_url(self, request: Request, token: str) -> str:
        """Build email verification URL."""
        if hasattr(settings, "FRONTEND_URL") and settings.FRONTEND_URL:
            base_url = settings.FRONTEND_URL
        else:
            scheme = "https" if request.is_secure() else "http"
            host = request.get_host()
            base_url = f"{scheme}://{host}"

        return f"{base_url}/verify-email?token={token}"

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0].strip()
        else:
            ip = str(request.META.get("REMOTE_ADDR", ""))
        return ip

    def post(self, request: Request) -> Response:
        """Handle user registration."""
        system_settings = PublicAccountSettings.get_settings()
        if not system_settings.registration_enabled:
            logger.warning(
                "Registration attempt blocked - registration is disabled",
                extra={"ip_address": self.get_client_ip(request)},
            )
            return Response(
                {"error": "Registration is currently disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            self.security_events.log_account_created(
                username=user.username,
                email=user.email,
                ip_address=self.get_client_ip(request),
            )

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
                    extra={"user_id": user.id, "email": user.email},
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
