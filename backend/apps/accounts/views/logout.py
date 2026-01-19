"""User logout view."""

from logging import Logger, getLogger
from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserSession
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.jwt import JWTService

logger: Logger = getLogger(name=__name__)


@extend_schema_view(
    post=extend_schema(
        summary="User logout",
        description="Logout user and terminate all active sessions. Requires valid JWT token in Authorization header.",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Logout successful",
                response={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "sessions_terminated": {"type": "integer"},
                    },
                },
            ),
            401: OpenApiResponse(description="Invalid or expired token"),
        },
        tags=["Authentication"],
    )
)
class UserLogoutView(APIView):
    """
    API endpoint for user logout.

    POST /api/auth/logout
    - Invalidate JWT token
    - Terminate user session
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize view with security event service."""
        super().__init__(**kwargs)
        self.security_events = SecurityEventService()

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0].strip()
        else:
            ip = str(request.META.get("REMOTE_ADDR", ""))
        return ip

    def post(self, request: Request) -> Response:
        """Handle user logout."""
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

        user = JWTService().get_user_from_token(token)
        if not user:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip_address = self.get_client_ip(request)

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

        self.security_events.log_logout(
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
