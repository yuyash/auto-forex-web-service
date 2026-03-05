"""
E2E test settings — uses real PostgreSQL and Redis.

Inherits from base settings and overrides only what's needed for E2E tests
running in GitHub Actions with service containers.
"""

import os

from config.settings import *  # noqa: F403, F401

# =============================================================================
# Database — real PostgreSQL (from CI service container)
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "test_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 10},
    }
}

# =============================================================================
# Cache — real Redis
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    }
}

# =============================================================================
# Celery — eager mode (synchronous) for E2E tests
# =============================================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# =============================================================================
# Channel Layers — in-memory for E2E tests
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# =============================================================================
# Session — use cache backend
# =============================================================================

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# =============================================================================
# Market Redis — real Redis for tick data
# =============================================================================

MARKET_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# =============================================================================
# Password Hashing — faster for tests
# =============================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# =============================================================================
# Security — relaxed for tests
# =============================================================================

SECRET_KEY = os.getenv(  # nosec B105
    "SECRET_KEY", "e2e-test-secret-key-for-ci-only-minimum-50-characters-long-enough"
)
JWT_SECRET_KEY = os.getenv(  # nosec B105
    "JWT_SECRET_KEY", "e2e-test-jwt-secret-key-for-ci-only-minimum-50-characters-long"
)
DEBUG = False
ALLOWED_HOSTS = ["*"]
SECURE_SSL_REDIRECT = False  # type: ignore[assignment]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False  # type: ignore[assignment]

# =============================================================================
# Email — console backend
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# Logging — minimal
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# =============================================================================
# OANDA API
# =============================================================================

OANDA_PRACTICE_API = "https://api-fxpractice.oanda.com"
OANDA_LIVE_API = "https://api-fxtrade.oanda.com"
OANDA_STREAM_TIMEOUT = 5
