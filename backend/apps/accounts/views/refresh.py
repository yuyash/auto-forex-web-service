"""JWT token refresh view."""

from logging import Logger, getLogger

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services.jwt import JWTService

logger: Logger = getLogger(name=__name__)


class TokenRefreshView(APIView):
    """
    API endpoint for JWT token refresh.

    POST /api/auth/refresh
    - Refresh JWT token if valid
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="POST /api/accounts/auth/refresh",
        description="Refresh an existing JWT token to extend its expiration time. "
        "Requires valid JWT token in Authorization header.",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Token refreshed successfully",
                response={
                    "type": "object",
                    "properties": {
                        "token": {"type": "string"},
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "email": {"type": "string"},
                                "username": {"type": "string"},
                                "is_staff": {"type": "boolean"},
                                "timezone": {"type": "string"},
                                "language": {"type": "string"},
                            },
                        },
                    },
                },
            ),
            401: OpenApiResponse(description="Invalid or expired token"),
            500: OpenApiResponse(description="Failed to retrieve user information"),
        },
        tags=["Authentication"],
    )
    def post(self, request: Request) -> Response:
        """Handle token refresh."""
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

        new_token = JWTService().refresh_token(token)
        if not new_token:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = JWTService().get_user_from_token(new_token)
        if not user:
            return Response(
                {"error": "Failed to retrieve user information."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "Token refreshed for user %s",
            user.email,
            extra={"user_id": user.id, "email": user.email},
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
