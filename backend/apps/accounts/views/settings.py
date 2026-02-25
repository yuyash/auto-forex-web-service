"""User settings and public account settings views."""

from logging import Logger, getLogger

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PublicAccountSettings, UserSettings
from apps.accounts.serializers import (
    PublicAccountSettingsSerializer,
    UserProfileSerializer,
    UserSettingsSerializer,
    UserSettingsUpdateSerializer,
)

logger: Logger = getLogger(name=__name__)


class UserSettingsView(APIView):
    """
    API endpoint for managing user settings.

    GET /api/settings
    - Get user settings including timezone, language, and strategy defaults

    PUT /api/settings
    - Update user settings
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSettingsUpdateSerializer

    @extend_schema(
        operation_id="user_settings_get",
        tags=["Accounts"],
        responses={
            200: inline_serializer(
                "UserSettingsResponse",
                fields={
                    "user": UserProfileSerializer(),
                    "settings": UserSettingsSerializer(),
                },
            ),
            401: inline_serializer(
                "UserSettingsUnauthorized", fields={"error": serializers.CharField()}
            ),
        },
    )
    def get(self, request: Request) -> Response:
        """Get user settings."""
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

        user_serializer = UserProfileSerializer(request.user)
        settings_serializer = UserSettingsSerializer(user_settings)

        response_data = {
            "user": user_serializer.data,
            "settings": settings_serializer.data,
        }

        logger.info(
            "User %s retrieved settings",
            request.user.email,
            extra={"user_id": request.user.id, "email": request.user.email},
        )

        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="user_settings_update",
        tags=["Accounts"],
        request=UserSettingsUpdateSerializer,
        responses={
            200: inline_serializer(
                "UserSettingsUpdateResponse",
                fields={
                    "user": UserProfileSerializer(),
                    "settings": UserSettingsSerializer(),
                },
            ),
            400: inline_serializer(
                "UserSettingsValidationError",
                fields={"detail": serializers.CharField(required=False)},
            ),
            401: inline_serializer(
                "UserSettingsUpdateUnauthorized", fields={"error": serializers.CharField()}
            ),
        },
    )
    def put(self, request: Request) -> Response:
        """Update user settings."""
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

        user_data = {}
        settings_data = {}

        user_fields = ["timezone", "language", "first_name", "last_name", "username"]
        for field in user_fields:
            if field in request.data:
                user_data[field] = request.data[field]

        settings_fields = [
            "notification_enabled",
            "notification_email",
            "notification_browser",
            "settings_json",
        ]
        for field in settings_fields:
            if field in request.data:
                settings_data[field] = request.data[field]

        user_serializer = UserProfileSerializer(request.user, data=user_data, partial=True)
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        settings_serializer = UserSettingsSerializer(
            user_settings, data=settings_data, partial=True
        )
        if not settings_serializer.is_valid():
            return Response(settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_serializer.save()
        settings_serializer.save()

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


class PublicAccountSettingsView(APIView):
    """
    API endpoint for public account settings (no authentication required).

    GET /api/accounts/settings/public
    - Return registration_enabled and login_enabled flags
    """

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="public_account_settings",
        tags=["Accounts"],
        responses={200: PublicAccountSettingsSerializer},
        description="Get public account settings (registration/login enabled flags).",
    )
    def get(self, request: Request) -> Response:  # pylint: disable=unused-argument
        """Get public account settings."""
        account_settings = PublicAccountSettings.get_settings()
        serializer = PublicAccountSettingsSerializer(account_settings)

        return Response(serializer.data, status=status.HTTP_200_OK)
