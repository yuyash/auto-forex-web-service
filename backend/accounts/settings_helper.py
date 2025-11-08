"""
Settings Helper

Provides functions to get system settings from the database.
Falls back to environment variables if database is not available.
"""

import os
from typing import Any

from django.core.cache import cache


def get_system_setting(key: str, default: Any = None) -> Any:
    """
    Get a system setting from the database with caching.
    Falls back to environment variable if database is not available.

    Args:
        key: Setting key name
        default: Default value if setting not found

    Returns:
        Setting value
    """
    try:
        from accounts.models import SystemSettings

        settings = cache.get("system_settings_obj")
        if settings is None:
            settings = SystemSettings.get_settings()
            cache.set("system_settings_obj", settings, 300)  # Cache for 5 minutes

        return getattr(settings, key, default)
    except Exception:
        # Database not available or other error, fall back to environment variable
        env_key = key.upper()
        return os.getenv(env_key, default)


def get_email_backend() -> str:
    """Get the email backend class based on settings."""
    backend_type = get_system_setting("email_backend_type", "smtp")
    if backend_type == "ses":
        return "django_ses.SESBackend"
    return "django.core.mail.backends.smtp.EmailBackend"


def get_email_config() -> dict:
    """Get email configuration from system settings."""
    return {
        "EMAIL_BACKEND": get_email_backend(),
        "EMAIL_HOST": get_system_setting("email_host", "smtp.gmail.com"),
        "EMAIL_PORT": get_system_setting("email_port", 587),
        "EMAIL_USE_TLS": get_system_setting("email_use_tls", True),
        "EMAIL_USE_SSL": get_system_setting("email_use_ssl", False),
        "EMAIL_HOST_USER": get_system_setting("email_host_user", ""),
        "EMAIL_HOST_PASSWORD": get_system_setting("email_host_password", ""),
        "DEFAULT_FROM_EMAIL": get_system_setting("default_from_email", "noreply@example.com"),
    }


def get_aws_config() -> dict:
    """Get AWS configuration from system settings."""
    return {
        "AWS_ACCESS_KEY_ID": get_system_setting("aws_access_key_id", ""),
        "AWS_SECRET_ACCESS_KEY": get_system_setting("aws_secret_access_key", ""),
        "AWS_REGION": get_system_setting("aws_region", "us-east-1"),
        "AWS_S3_BUCKET": get_system_setting("aws_s3_bucket", ""),
        "AWS_SES_REGION": get_system_setting("aws_ses_region", "us-east-1"),
    }


def refresh_settings_cache() -> None:
    """Clear the settings cache to force reload."""
    cache.delete("system_settings_obj")
