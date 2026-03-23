"""User logout view."""

from logging import Logger, getLogger
from typing import Any, cast

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserSession
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.jwt import JWTService
from apps.accounts.utils.cookies import clear_refresh_cookie

logger: Logger = getLogger(name=__name__)


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

    @extend_schema(
        operation_id="auth_logout",
        tags=["Accounts"],
        request=None,
        responses={
            200: inline_serializer(
                "LogoutResponse",
                fields={
                    "message": serializers.CharField(),
                    "sessions_terminated": serializers.IntegerField(),
                },
            ),
            401: inline_serializer(
                "LogoutError",
                fields={"error": serializers.CharField()},
            ),
        },
        description="Invalidate JWT token and terminate user sessions.",
    )
    def post(self, request: Request) -> Response:
        """Handle user logout."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        user_obj = getattr(request, "user", None)
        if not auth_header.startswith("Bearer ") or not isinstance(user_obj, User):
            response = Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_refresh_cookie(response)
        auth_user = cast(User, user_obj)

        ip_address = self.get_client_ip(request)

        active_sessions = UserSession.objects.filter(user=auth_user, is_active=True)
        for session in active_sessions:
            session.terminate()

        # Revoke all refresh tokens for this user
        revoked_count = JWTService.revoke_all_refresh_tokens(auth_user)

        logger.info(
            "User %s logged out successfully from %s",
            auth_user.email,
            ip_address,
            extra={
                "user_id": auth_user.pk,
                "email": auth_user.email,
                "ip_address": ip_address,
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "sessions_terminated": active_sessions.count(),
                "refresh_tokens_revoked": revoked_count,
            },
        )

        self.security_events.log_logout(
            user=auth_user,
            ip_address=ip_address,
        )

        response = Response(
            {
                "message": "Logged out successfully.",
                "sessions_terminated": active_sessions.count(),
            },
            status=status.HTTP_200_OK,
        )
        return clear_refresh_cookie(response)
