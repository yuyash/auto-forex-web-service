"""Shared utilities for account middlewares."""

from typing import Any, cast

from django.http import HttpRequest

from apps.accounts.models import User


def get_client_ip(request: HttpRequest) -> str:
    """Extract the client IP address from the request.

    Checks ``X-Forwarded-For`` first (set by reverse proxies like nginx),
    then falls back to ``REMOTE_ADDR``.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return str(request.META.get("REMOTE_ADDR", ""))


def get_authenticated_user(user: Any) -> User | None:
    """Return the authenticated ``User`` instance, or ``None``."""
    if user is not None and bool(getattr(user, "is_authenticated", False)):
        return cast(User, user)
    return None
