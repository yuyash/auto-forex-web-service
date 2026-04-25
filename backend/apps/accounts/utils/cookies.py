"""Cookie helpers for auth-related responses."""

from __future__ import annotations

from rest_framework.response import Response


def set_refresh_cookie(response: Response, refresh_token: str) -> Response:
    """Attach the configured refresh-token cookie to a response."""
    from django.conf import settings

    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE,
        httponly=settings.AUTH_REFRESH_COOKIE_HTTPONLY,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN,
    )
    return response


def set_access_cookie(response: Response, access_token: str) -> Response:
    """Attach the configured access-token cookie to a response."""
    from django.conf import settings

    response.set_cookie(
        settings.AUTH_ACCESS_COOKIE_NAME,
        access_token,
        max_age=settings.JWT_EXPIRATION_DELTA,
        httponly=settings.AUTH_ACCESS_COOKIE_HTTPONLY,
        secure=settings.AUTH_ACCESS_COOKIE_SECURE,
        samesite=settings.AUTH_ACCESS_COOKIE_SAMESITE,
        path=settings.AUTH_ACCESS_COOKIE_PATH,
        domain=settings.AUTH_ACCESS_COOKIE_DOMAIN,
    )
    return response


def clear_refresh_cookie(response: Response) -> Response:
    """Remove the configured refresh-token cookie from a response."""
    from django.conf import settings

    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )
    return response


def clear_access_cookie(response: Response) -> Response:
    """Remove the configured access-token cookie from a response."""
    from django.conf import settings

    response.delete_cookie(
        settings.AUTH_ACCESS_COOKIE_NAME,
        path=settings.AUTH_ACCESS_COOKIE_PATH,
        domain=settings.AUTH_ACCESS_COOKIE_DOMAIN,
        samesite=settings.AUTH_ACCESS_COOKIE_SAMESITE,
    )
    return response


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> Response:
    """Attach both auth cookies to a response."""
    set_access_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token)
    return response


def clear_auth_cookies(response: Response) -> Response:
    """Remove all configured auth cookies from a response."""
    clear_access_cookie(response)
    clear_refresh_cookie(response)
    return response
