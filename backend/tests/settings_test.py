"""
Django test settings for integration tests.

This settings module extends the base settings with test-specific overrides:
- Uses SQLite in-memory database for faster tests
- Disables external services (email, Celery)
- Simplifies middleware for testing
"""

import os
import uuid

# Set environment to test mode
os.environ.setdefault("DJANGO_ENV", "development")

# Import all settings from the main settings module
from config.settings import *  # noqa: E402, F401, F403

# Use test-only URL routing so integration tests can hit market endpoints
# without requiring production wiring changes.
ROOT_URLCONF = "tests.urls_test"

# =============================================================================
# Test-specific Database Configuration
# =============================================================================


_test_db_name = f"/tmp/test_db_{uuid.uuid4().hex}.sqlite3"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _test_db_name,
        "TEST": {
            "NAME": _test_db_name,
        },
    }
}

# =============================================================================
# Test-specific Settings
# =============================================================================

# Disable password hashing for faster tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Simplified middleware for tests (remove custom middleware that may cause issues)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Use in-memory email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable cache for tests - use dummy cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Faster JWT validation in tests
JWT_EXPIRATION = 3600  # 1 hour

# Disable rate limiting for tests
RATE_LIMIT_ENABLED = False

# Debug mode for tests
DEBUG = True

# =============================================================================
# Security Settings for Tests (Disable HTTPS/SSL requirements)
# =============================================================================

# Disable SSL redirect for live_server tests
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Disable secure cookies for tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Allow all hosts in tests
ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1", "testserver"]

# Use simple ASGI for tests (no channels layer)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Logging configuration for tests (reduce noise)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# REST Framework settings for tests
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
