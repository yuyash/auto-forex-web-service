"""
Test-specific Django settings.

This module extends the base settings with test-specific configurations:
- Test database configuration
- In-memory cache for faster tests
- Celery eager mode for synchronous task execution
- Disabled external API calls
- Simplified logging
"""

import os

os.environ.setdefault(
    "OANDA_TOKEN_ENCRYPTION_KEY",
    "0VnOF0t7mggT8F_hLto5Q4TbsS5k8M_3xK6HDhM2sLo=",
)

from config.settings import *  # noqa: F403

# =============================================================================
# Test Database Configuration
# =============================================================================

PYTEST_XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER")
SQLITE_TEST_DB_NAME = (
    f"test_db_{PYTEST_XDIST_WORKER}.sqlite3" if PYTEST_XDIST_WORKER else "test_db.sqlite3"
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / SQLITE_TEST_DB_NAME),  # noqa: F405
    }
}

# =============================================================================
# Cache Configuration (In-Memory for Tests)
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# =============================================================================
# Celery Configuration (Eager Mode for Synchronous Execution)
# =============================================================================

# Execute tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory broker for tests
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# =============================================================================
# Session Configuration
# =============================================================================

# Use in-memory cache for sessions in tests
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# =============================================================================
# Password Hashing (Faster for Tests)
# =============================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# =============================================================================
# Logging Configuration (Simplified for Tests)
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
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# =============================================================================
# Security Settings (Relaxed for Tests)
# =============================================================================

SECRET_KEY = "test-secret-key-not-for-production"  # nosec B105 - Test environment only
DEBUG = False  # Keep False to test production-like behavior
ALLOWED_HOSTS = ["*"]

# Disable HTTPS requirements in tests
SECURE_SSL_REDIRECT = False  # type: ignore[assignment]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False  # type: ignore[assignment]

# =============================================================================
# Email Configuration (Console Backend for Tests)
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# Static Files (Disable Collection in Tests)
# =============================================================================

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# =============================================================================
# Market Data Configuration (Disable Real Streaming in Tests)
# =============================================================================

# Use mock Redis for market data in tests
MARKET_REDIS_URL = "redis://localhost:6379/3"

# =============================================================================
# OANDA API Configuration (Use Practice API in Tests)
# =============================================================================

OANDA_PRACTICE_API = "https://api-fxpractice.oanda.com"
OANDA_LIVE_API = "https://api-fxtrade.oanda.com"
OANDA_STREAM_TIMEOUT = 5  # Shorter timeout for tests
OANDA_REST_TIMEOUT = 5
OANDA_REST_MAX_RETRIES = 0

# =============================================================================
# Rate Limiting — disabled for tests
# =============================================================================

REST_FRAMEWORK = {
    **globals().get("REST_FRAMEWORK", {}),  # type: ignore[arg-type]
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "task_data": "6000/minute",
    },
}
