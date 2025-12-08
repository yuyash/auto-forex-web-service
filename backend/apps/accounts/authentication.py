"""
JWT authentication backend for Django REST Framework.

This module provides JWT token authentication for API endpoints.
"""

from typing import Any, Optional, Tuple

from django.contrib.auth import get_user_model

from rest_framework import authentication, exceptions
from rest_framework.request import Request

from .jwt_utils import get_user_from_token

User = get_user_model()


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT token authentication backend.

    Authenticates users based on JWT tokens in the Authorization header.
    Expected format: Authorization: Bearer <token>
    """

    keyword = "Bearer"

    def authenticate(self, request: Request) -> Optional[Tuple[Any, str]]:
        """
        Authenticate the request using JWT token.

        Args:
            request: HTTP request

        Returns:
            Tuple of (user, token) if authentication succeeds, None otherwise

        Raises:
            AuthenticationFailed: If token is invalid or expired
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None
        auth_parts = auth_header.split()
        if len(auth_parts) != 2:
            return None
        if auth_parts[0] != self.keyword:
            return None
        token = auth_parts[1]
        return self.authenticate_credentials(token)

    def authenticate_credentials(self, token: str) -> Tuple[Any, str]:
        """
        Validate token and return user.

        Args:
            token: JWT token string

        Returns:
            Tuple of (user, token)

        Raises:
            AuthenticationFailed: If token is invalid or expired
        """
        user = get_user_from_token(token)
        if user is None:
            raise exceptions.AuthenticationFailed("Invalid or expired token.")
        if not user.is_active:
            raise exceptions.AuthenticationFailed("User account is disabled.")
        if user.is_locked:
            raise exceptions.AuthenticationFailed("User account is locked.")
        return (user, token)

    def authenticate_header(self, request: Request) -> str:
        """
        Return the authentication header value.

        Args:
            request: HTTP request

        Returns:
            Authentication header value
        """
        return self.keyword
