"""
WebSocket authentication middleware for JWT tokens.

This module provides middleware to authenticate WebSocket connections
using JWT tokens passed in the query string or headers.
"""

import logging
from typing import Any, Dict
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from .jwt_utils import get_user_from_token

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens.

    This middleware:
    - Extracts JWT token from query string (?token=xxx) or headers
    - Validates the token and retrieves the user
    - Adds the user to the WebSocket scope
    - Falls back to AnonymousUser if token is invalid or missing
    """

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> Any:
        """
        Process the WebSocket connection and authenticate the user.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable

        Returns:
            Result of calling the inner application
        """
        # Only process WebSocket connections
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        # Try to get token from query string
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        # If no token in query string, try headers
        if not token:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Authenticate user with token
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
        """
        Get user from JWT token (database sync to async wrapper).

        Args:
            token: JWT token string

        Returns:
            User instance if token is valid, None otherwise
        """
        return get_user_from_token(token)


def JWTAuthMiddlewareStack(inner: Any) -> Any:  # pylint: disable=invalid-name
    """
    Convenience function to apply JWT authentication middleware.

    Args:
        inner: Inner ASGI application

    Returns:
        Wrapped application with JWT authentication
    """
    return JWTAuthMiddleware(inner)
