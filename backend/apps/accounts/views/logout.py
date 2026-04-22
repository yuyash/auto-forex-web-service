"""User logout view."""

from logging import Logger, getLogger
from typing import Any, cast

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middlewares.utils import get_client_ip
from apps.accounts.models import RefreshToken, User
from apps.accounts.services.events import SecurityEventService
from apps.accounts.services.jwt import JWTService
from apps.accounts.services.sessions import get_user_session_for_request
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

        ip_address = get_client_ip(request)
        current_session = get_user_session_for_request(request, auth_user)
        sessions_terminated = 0
        if current_session and current_session.is_active:
            current_session.terminate()
            sessions_terminated = 1

        refresh_cookie_name = getattr(request, "COOKIES", {}).get
        refresh_token_value = str(
            refresh_cookie_name("refresh_token", "")
            if callable(refresh_cookie_name)
            else request.COOKIES.get("refresh_token", "")
        ).strip()
        revoked_count = 0
        if refresh_token_value:
            token_hash = JWTService.hash_refresh_token(refresh_token_value)
            refresh_token = (
                RefreshToken.objects.filter(user=auth_user, token=token_hash)
                .select_related("session")
                .first()
            )
            if refresh_token is None:
                refresh_token = (
                    RefreshToken.objects.filter(user=auth_user, token=refresh_token_value)
                    .select_related("session")
                    .first()
                )
            if refresh_token and refresh_token.session_id:
                revoked_count = JWTService.revoke_refresh_tokens_for_session(refresh_token.session)

        if revoked_count == 0 and current_session is not None:
            revoked_count = JWTService.revoke_refresh_tokens_for_session(current_session)

        logger.info(
            "User %s logged out successfully from %s",
            auth_user.email,
            ip_address,
            extra={
                "user_id": auth_user.pk,
                "email": auth_user.email,
                "ip_address": ip_address,
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "sessions_terminated": sessions_terminated,
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
                "sessions_terminated": sessions_terminated,
            },
            status=status.HTTP_200_OK,
        )
        return clear_refresh_cookie(response)
