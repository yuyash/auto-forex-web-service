"""
JWT authentication backend for Django REST Framework.

This module provides JWT token authentication for API endpoints.
"""

from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import authentication, exceptions
from rest_framework.request import Request

from apps.accounts.services.jwt import JWTService


class CSRFCheck(CsrfViewMiddleware):
    """Return CSRF failure reasons instead of full HttpResponse objects."""

    def _reject(self, request: Request, reason: str) -> str:
        return reason


def enforce_csrf(request: Request) -> None:
    """Require Django's CSRF token for a DRF request."""
    django_request = cast(HttpRequest, getattr(request, "_request", request))
    check = CSRFCheck(lambda req: None)
    csrf_checks_disabled = getattr(django_request, "_dont_enforce_csrf_checks", None)
    setattr(django_request, "_dont_enforce_csrf_checks", False)
    try:
        check.process_request(django_request)
        reason = check.process_view(django_request, lambda req: None, (), {})
    finally:
        if csrf_checks_disabled is None:
            delattr(django_request, "_dont_enforce_csrf_checks")
        else:
            setattr(django_request, "_dont_enforce_csrf_checks", csrf_checks_disabled)
    if reason:
        raise exceptions.PermissionDenied("CSRF verification failed.")


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT token authentication backend.

    Authenticates users based on JWT tokens in the Authorization header.
    Expected format: Authorization: Bearer <token>
    """

    keyword = "Bearer"
    safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}

    def authenticate(self, request: Request) -> tuple[Any, str] | None:
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
            cookies = getattr(request, "COOKIES", {})
            token = (
                cookies.get(settings.AUTH_ACCESS_COOKIE_NAME) if isinstance(cookies, dict) else None
            )
            if not token:
                return None
            self._enforce_csrf_for_cookie_auth(request)
            return self.authenticate_credentials(token)

        auth_parts = auth_header.split()
        if len(auth_parts) != 2:
            return None
        if auth_parts[0] != self.keyword:
            return None
        token = auth_parts[1]
        return self.authenticate_credentials(token)

    def authenticate_credentials(self, token: str) -> tuple[Any, str]:
        """
        Validate token and return user.

        Args:
            token: JWT token string

        Returns:
            Tuple of (user, token)

        Raises:
            AuthenticationFailed: If token is invalid or expired
        """
        user = JWTService().get_user_from_token(token)
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

    def _enforce_csrf_for_cookie_auth(self, request: Request) -> None:
        """Require Django's CSRF token when authenticating unsafe cookie requests."""
        if request.method in self.safe_methods:
            return
        enforce_csrf(request)
