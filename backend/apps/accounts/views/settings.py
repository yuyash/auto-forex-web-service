"""User settings and public account settings views."""

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import PublicAccountSettings, UserSettings
from apps.accounts.serializers import (
    PublicAccountSettingsSerializer,
    UserProfileSerializer,
    UserSettingsSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        summary="Get user settings",
        description="Retrieve user profile and settings including timezone, language, and notification preferences.",
        responses={
            200: OpenApiResponse(
                description="User settings retrieved successfully",
                response={
                    "type": "object",
                    "properties": {
                        "user": {"$ref": "#/components/schemas/UserProfile"},
                        "settings": {"$ref": "#/components/schemas/UserSettings"},
                    },
                },
            ),
            401: OpenApiResponse(description="Authentication required"),
        },
        tags=["User Settings"],
    ),
    put=extend_schema(
        summary="Update user settings",
        description="Update user profile and settings. Can update timezone, language, notification preferences, etc.",
        request={
            "type": "object",
            "properties": {
                "timezone": {"type": "string"},
                "language": {"type": "string", "enum": ["en", "ja"]},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "username": {"type": "string"},
                "notification_enabled": {"type": "boolean"},
                "notification_email": {"type": "boolean"},
                "notification_browser": {"type": "boolean"},
                "settings_json": {"type": "object"},
            },
        },
        responses={
            200: OpenApiResponse(description="Settings updated successfully"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
        },
        tags=["User Settings"],
    ),
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


@extend_schema_view(
    get=extend_schema(
        summary="Get public account settings",
        description="Retrieve public account settings including registration and login availability. "
        "No authentication required.",
        responses={
            200: OpenApiResponse(
                description="Public settings retrieved successfully",
                response=PublicAccountSettingsSerializer,
            ),
        },
        tags=["Public Settings"],
    )
)
class PublicAccountSettingsView(APIView):
    """
    API endpoint for public account settings (no authentication required).

    GET /api/accounts/settings/public
    - Return registration_enabled and login_enabled flags
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:  # pylint: disable=unused-argument
        """Get public account settings."""
        account_settings = PublicAccountSettings.get_settings()
        serializer = PublicAccountSettingsSerializer(account_settings)

        return Response(serializer.data, status=status.HTTP_200_OK)
