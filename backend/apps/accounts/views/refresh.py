"""JWT token refresh view using opaque refresh tokens."""

from logging import Logger, getLogger

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services.jwt import JWTService

logger: Logger = getLogger(name=__name__)


class TokenRefreshView(APIView):
    """
    API endpoint for JWT token refresh using opaque refresh tokens.

    POST /api/auth/refresh
    - Exchange a valid refresh_token for a new access + refresh token pair
    - The old refresh token is revoked (rotation)
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return str(request.META.get("REMOTE_ADDR", ""))

    @extend_schema(
        operation_id="auth_token_refresh",
        tags=["Accounts"],
        request=inline_serializer(
            "TokenRefreshRequest",
            fields={"refresh_token": serializers.CharField()},
        ),
        responses={
            200: inline_serializer(
                "TokenRefreshResponse",
                fields={
                    "token": serializers.CharField(),
                    "refresh_token": serializers.CharField(),
                    "user": inline_serializer(
                        "TokenRefreshUser",
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
            401: inline_serializer(
                "TokenRefreshError",
                fields={"error": serializers.CharField()},
            ),
        },
        description="Exchange a refresh token for a new access + refresh token pair.",
    )
    def post(self, request: Request) -> Response:
        """Handle token refresh via opaque refresh token."""
        refresh_token_value = request.data.get("refresh_token", "").strip()
        if not refresh_token_value:
            return Response(
                {"error": "refresh_token is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        result = JWTService().rotate_refresh_token(
            refresh_token_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if result is None:
            logger.warning(
                "Refresh token rejected (invalid/expired/revoked) from %s",
                ip_address,
            )
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_access, new_refresh, user = result

        logger.info(
            "Token refreshed for user %s",
            user.email,
            extra={"user_id": user.id, "email": user.email},
        )

        return Response(
            {
                "token": new_access,
                "refresh_token": new_refresh,
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
