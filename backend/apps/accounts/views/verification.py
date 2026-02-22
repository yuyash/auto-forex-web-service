"""Email verification views."""

from logging import Logger, getLogger

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import EmailVerificationSerializer, ResendVerificationSerializer
from apps.accounts.services.email import AccountEmailService

logger: Logger = getLogger(name=__name__)


class EmailVerificationView(APIView):
    """
    API endpoint for email verification.

    POST /api/auth/verify-email
    - Verify user email with token
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = EmailVerificationSerializer

    @extend_schema(
        summary="POST /api/accounts/auth/verify-email",
        description="Verify user email address using the verification token sent via email.",
        request=EmailVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Email verified successfully"),
            400: OpenApiResponse(description="Invalid or expired token"),
        },
        tags=["Authentication"],
    )
    def post(self, request: Request) -> Response:
        """Verify user email with token."""
        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.verify_email(token):
            AccountEmailService().send_welcome_message(
                user,
                sender=self.__class__,
            )

            logger.info(
                "Email verified for user %s",
                user.email,
                extra={"user_id": user.pk, "email": user.email},
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
    authentication_classes: list = []
    serializer_class = ResendVerificationSerializer

    def build_verification_url(self, request: Request, token: str) -> str:
        """Build email verification URL."""
        if hasattr(settings, "FRONTEND_URL") and settings.FRONTEND_URL:
            base_url = settings.FRONTEND_URL
        else:
            scheme = "https" if request.is_secure() else "http"
            host = request.get_host()
            base_url = f"{scheme}://{host}"

        return f"{base_url}/verify-email?token={token}"

    @extend_schema(
        summary="POST /api/accounts/auth/resend-verification",
        description="Resend email verification link to the specified email address.",
        request=ResendVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Verification email sent"),
            400: OpenApiResponse(description="Email is required or already verified"),
        },
        tags=["Authentication"],
    )
    def post(self, request: Request) -> Response:
        """Resend verification email."""
        email = request.data.get("email", "").lower()

        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {
                    "message": (
                        "If an account with this email exists and is not verified, "
                        "a verification email will be sent."
                    )
                },
                status=status.HTTP_200_OK,
            )

        if user.email_verified:
            return Response(
                {"error": "Email is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                extra={"user_id": user.pk, "email": user.email},
            )

        return Response(
            {
                "message": "Verification email sent. Please check your inbox.",
                "email_sent": email_sent,
            },
            status=status.HTTP_200_OK,
        )
