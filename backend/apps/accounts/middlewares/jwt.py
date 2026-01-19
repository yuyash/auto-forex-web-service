"""JWT authentication middleware for WebSocket connections."""

from logging import Logger, getLogger
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from apps.accounts.services.jwt import JWTService

logger: Logger = getLogger(name=__name__)


class JWTAuthMiddleware(BaseMiddleware):
    """Custom middleware to authenticate WebSocket connections using JWT tokens."""

    def __init__(self, inner: Any) -> None:
        """Initialize the middleware with the inner application."""
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        """Process the WebSocket connection and authenticate the user."""
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if not token:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if token:
            user = await self.get_user_from_token(token)
            if user:
                scope["user"] = user
                logger.debug(
                    "WebSocket authenticated user %s",
                    user.username,
                )
            else:
                scope["user"] = AnonymousUser()
                logger.warning("Invalid JWT token in WebSocket connection")
        else:
            scope["user"] = AnonymousUser()
            logger.debug("No JWT token provided in WebSocket connection")

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token: str) -> Any:
        """Get user from JWT token (database sync to async wrapper)."""
        return JWTService().get_user_from_token(token)


def jwt_auth_middleware_stack(inner: Any) -> Any:
    """Convenience function to apply JWT authentication middleware."""
    return JWTAuthMiddleware(inner)
