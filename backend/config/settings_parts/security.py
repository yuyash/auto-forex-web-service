"""Security and auth-cookie settings helpers."""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from typing import Any

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured


def build_runtime_environment(*, debug: bool) -> dict[str, Any]:
    """Return environment flags shared across settings sections."""
    settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "")
    is_test_env = settings_module.endswith(("settings_test", "settings_e2e")) or any(
        arg in {"pytest", "py.test"} or arg.endswith("/pytest") for arg in sys.argv
    )
    is_local_env = os.getenv("DJANGO_ENV", "development").strip().lower() in {
        "development",
        "dev",
        "local",
    }
    return {
        "DJANGO_SETTINGS_MODULE": settings_module,
        "IS_TEST_ENV": is_test_env,
        "IS_LOCAL_ENV": is_local_env,
        "IS_NON_PRODUCTION_ENV": debug or is_test_env or is_local_env,
    }


def build_secret_settings(*, debug: bool) -> dict[str, Any]:
    """Return secret-key and JWT settings with production guards."""
    runtime = build_runtime_environment(debug=debug)
    is_non_production_env = runtime["IS_NON_PRODUCTION_ENV"]

    default_secret_key = "django-insecure-*6sf5x8=a0@4y+y1wwckk&vlp+)nv5%gl+-az@tt*ahkx3zav0"  # nosec B105
    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key:
        if is_non_production_env:
            secret_key = default_secret_key
        else:
            raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")

    if not is_non_production_env and secret_key == default_secret_key:
        raise ImproperlyConfigured("Refusing to start production with the default SECRET_KEY.")

    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not jwt_secret:
        if is_non_production_env:
            import warnings

            warnings.warn(
                "JWT_SECRET_KEY is not set — falling back to SECRET_KEY. "
                "Set a dedicated JWT_SECRET_KEY in production.",
                stacklevel=1,
            )
            jwt_secret = secret_key
        else:
            raise ImproperlyConfigured("JWT_SECRET_KEY must be set when DEBUG is False.")

    if not is_non_production_env and jwt_secret == secret_key:
        raise ImproperlyConfigured(
            "JWT_SECRET_KEY must be different from SECRET_KEY in production."
        )

    refresh_token_expiration = int(os.getenv("REFRESH_TOKEN_EXPIRATION", "604800"))
    legacy_oanda_key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest())
    oanda_key = os.getenv("OANDA_TOKEN_ENCRYPTION_KEY", "").strip()
    if not oanda_key:
        if is_non_production_env:
            import warnings

            warnings.warn(
                "OANDA_TOKEN_ENCRYPTION_KEY is not set - falling back to a key derived from "
                "SECRET_KEY. Set a dedicated Fernet key in production.",
                stacklevel=1,
            )
            oanda_key = legacy_oanda_key.decode("utf-8")
        else:
            raise ImproperlyConfigured(
                "OANDA_TOKEN_ENCRYPTION_KEY must be set to a valid Fernet key when DEBUG is False."
            )

    try:
        Fernet(oanda_key.encode("utf-8"))
    except Exception as exc:
        raise ImproperlyConfigured(
            "OANDA_TOKEN_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc

    oanda_fallback_keys = [
        key.strip()
        for key in os.getenv("OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS", "").split(",")
        if key.strip()
    ]
    # Only add the legacy SECRET_KEY-derived key as a fallback in non-production
    # environments. In production, fallback keys must be explicitly configured
    # via OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS to avoid silent breakage when
    # SECRET_KEY is rotated.
    if is_non_production_env and legacy_oanda_key.decode("utf-8") != oanda_key:
        oanda_fallback_keys.append(legacy_oanda_key.decode("utf-8"))

    validated_fallback_keys: list[str] = []
    for key in oanda_fallback_keys:
        try:
            Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise ImproperlyConfigured(
                "OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS must only contain valid Fernet keys."
            ) from exc
        if key not in validated_fallback_keys and key != oanda_key:
            validated_fallback_keys.append(key)

    return {
        **runtime,
        "SECRET_KEY": secret_key,
        "JWT_SECRET_KEY": jwt_secret,
        "JWT_ALGORITHM": "HS256",
        "OANDA_TOKEN_ENCRYPTION_KEY": oanda_key,
        "OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS": validated_fallback_keys,
        "REFRESH_TOKEN_EXPIRATION": refresh_token_expiration,
        "AUTH_REFRESH_COOKIE_NAME": os.getenv("AUTH_REFRESH_COOKIE_NAME", "refresh_token"),
        "AUTH_REFRESH_COOKIE_HTTPONLY": True,
        "AUTH_REFRESH_COOKIE_SECURE": (
            os.getenv("AUTH_REFRESH_COOKIE_SECURE", "true" if not debug else "false").lower()
            in {"true", "1", "yes", "on"}
        ),
        "AUTH_REFRESH_COOKIE_SAMESITE": os.getenv("AUTH_REFRESH_COOKIE_SAMESITE", "Lax"),
        "AUTH_REFRESH_COOKIE_PATH": os.getenv("AUTH_REFRESH_COOKIE_PATH", "/api/accounts/auth/"),
        "AUTH_REFRESH_COOKIE_DOMAIN": os.getenv("AUTH_REFRESH_COOKIE_DOMAIN") or None,
        "AUTH_REFRESH_COOKIE_MAX_AGE": refresh_token_expiration,
    }


def build_security_settings(*, debug: bool) -> dict[str, Any]:
    """Return Django security and CORS settings."""
    data: dict[str, Any] = {
        "CSP_DEFAULT_SRC": os.getenv("CSP_DEFAULT_SRC", "'self'"),
        "CSP_SCRIPT_SRC": os.getenv("CSP_SCRIPT_SRC", "'self'"),
        "CSP_STYLE_SRC": os.getenv("CSP_STYLE_SRC", "'self' 'unsafe-inline'"),
        "CSP_IMG_SRC": os.getenv("CSP_IMG_SRC", "'self' data:"),
        "CSP_CONNECT_SRC": os.getenv("CSP_CONNECT_SRC", "'self'"),
        "CORS_ALLOWED_ORIGINS": os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(
            ","
        ),
        "CORS_ALLOW_CREDENTIALS": True,
    }

    if not debug:
        data.update(
            {
                "SECURE_SSL_REDIRECT": True,
                "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
                "SECURE_HSTS_SECONDS": 31536000,
                "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
                "SECURE_HSTS_PRELOAD": True,
                "SECURE_CONTENT_TYPE_NOSNIFF": True,
                "SECURE_BROWSER_XSS_FILTER": True,
                "X_FRAME_OPTIONS": "DENY",
                "CSRF_COOKIE_SECURE": True,
                "SESSION_COOKIE_SECURE": True,
            }
        )

    return data
