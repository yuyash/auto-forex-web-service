"""JWT token refresh view using opaque refresh tokens."""

from logging import Logger, getLogger
from typing import cast

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middlewares.utils import get_client_ip
from apps.accounts.services.jwt import JWTService
from apps.accounts.utils.cookies import clear_auth_cookies, set_auth_cookies

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

    @extend_schema(
        operation_id="auth_token_refresh",
        tags=["Accounts"],
        request=inline_serializer(
            "TokenRefreshRequest",
            fields={"refresh_token": serializers.CharField(required=False, allow_blank=True)},
        ),
        responses={
            200: inline_serializer(
                "TokenRefreshResponse",
                fields={
                    "token": serializers.CharField(),
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
        description=(
            "Exchange a refresh token for a new access + refresh token pair. "
            "The refresh token is normally read from the HTTP-only cookie; the "
            "`refresh_token` request field is accepted only as a legacy fallback."
        ),
    )
    def post(self, request: Request) -> Response:
        """Handle token refresh via opaque refresh token."""
        refresh_token_value = str(
            request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
        ).strip()
        if not refresh_token_value:
            response = Response(
                {"error": "refresh token cookie is required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_auth_cookies(response)

        ip_address = get_client_ip(request)
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
            response = Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_auth_cookies(response)

        new_access, new_refresh, user = result

        logger.info(
            "Token refreshed for user %s",
            user.email,
            extra={"user_id": user.id, "email": user.email},
        )

        response = Response(
            {
                "token": new_access,
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
        return set_auth_cookies(response, access_token=new_access, refresh_token=new_refresh)
