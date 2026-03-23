"""
Django settings for auto_forex project.

Auto Forex Trader Backend Configuration

Configuration is done via environment variables and this settings file.
- .env file: Secrets (passwords, keys, credentials)
- Environment variables: Configuration overrides
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from config.settings_parts.celery import build_celery_settings
from config.settings_parts.logging import build_logging_settings
from config.settings_parts.rest import build_rest_settings
from config.settings_parts.security import build_secret_settings, build_security_settings
from config.version import get_version

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file in project root.
# Shell/container environment should take precedence over local .env values.
load_dotenv(BASE_DIR.parent / ".env", override=False)

# =============================================================================
# Server Configuration
# =============================================================================

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
_secret_settings = build_secret_settings(debug=DEBUG)
SECRET_KEY = _secret_settings["SECRET_KEY"]
IS_TEST_ENV = _secret_settings["IS_TEST_ENV"]
IS_LOCAL_ENV = _secret_settings["IS_LOCAL_ENV"]
IS_NON_PRODUCTION_ENV = _secret_settings["IS_NON_PRODUCTION_ENV"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


# Application definition

INSTALLED_APPS = [
    # Django Channels must be before django.contrib.staticfiles
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "channels",
    "django_celery_beat",
    # Local apps
    "apps.accounts",
    "apps.health",
    "apps.market",
    "apps.trading",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.accounts.middlewares.csp.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Custom security and logging middleware
    "apps.accounts.middlewares.logging.HTTPAccessLoggingMiddleware",
    "apps.accounts.middlewares.security.SecurityMonitoringMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# =============================================================================
# Database Configuration
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.getenv("DB_NAME", "auto-forex"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "postgres"),
        "PORT": os.getenv("DB_PORT", "5432"),
        # In development we default to non-persistent DB connections to avoid
        # exhausting Postgres max_connections when running multiple local processes.
        "CONN_MAX_AGE": int(
            os.getenv(
                "DB_CONN_MAX_AGE",
                (
                    "0"
                    if os.getenv("DJANGO_ENV", "development").strip().lower()
                    in {"development", "dev", "local"}
                    else "600"
                ),
            )
        ),
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}


# =============================================================================
# Redis Configuration
# =============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

REDIS_URL = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)


# =============================================================================
# Cache Configuration (Redis)
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "db": REDIS_DB,
            "pool_class": "redis.BlockingConnectionPool",
        },
        "KEY_PREFIX": "auto_forex",
        "TIMEOUT": 300,
    }
}


# =============================================================================
# Session Configuration (Redis)
# =============================================================================

# Security settings
JWT_EXPIRATION = int(os.getenv("JWT_EXPIRATION", "3600"))  # 1 hour
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION = int(os.getenv("LOCKOUT_DURATION", "900"))  # 15 minutes
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 1 minute

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = JWT_EXPIRATION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"


# =============================================================================
# Django Channels Configuration
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL.replace(f"/{REDIS_DB}", "/1")],  # Use db 1 for channels
            "capacity": 1500,
            "expiry": 10,
        },
    },
}


# =============================================================================
# Celery Configuration
# =============================================================================

globals().update(build_celery_settings(REDIS_URL, REDIS_DB))


# =============================================================================
# Market Tick Pub/Sub
# =============================================================================

REDIS_MARKET_DB = int(os.getenv("REDIS_MARKET_DB", "3"))
MARKET_REDIS_URL = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_MARKET_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_MARKET_DB}"
)

MARKET_TICK_CHANNEL = os.getenv("MARKET_TICK_CHANNEL", "market:ticks")
MARKET_TICK_INSTRUMENTS = [
    x.strip() for x in os.getenv("MARKET_TICK_INSTRUMENTS", "EUR_USD").split(",") if x.strip()
]

MARKET_TICK_PUBSUB_INIT_KEY = os.getenv("MARKET_TICK_PUBSUB_INIT_KEY", "market:tick_pubsub:init")
MARKET_TICK_ACCOUNT_KEY = os.getenv("MARKET_TICK_ACCOUNT_KEY", "market:tick_pubsub:account")
MARKET_TICK_PUBLISHER_LOCK_KEY = os.getenv(
    "MARKET_TICK_PUBLISHER_LOCK_KEY", "market:tick_publisher:lock"
)
MARKET_TICK_SUBSCRIBER_LOCK_KEY = os.getenv(
    "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock"
)
MARKET_TICK_SUPERVISOR_LOCK_KEY = os.getenv(
    "MARKET_TICK_SUPERVISOR_LOCK_KEY", "market:tick_supervisor:lock"
)
MARKET_TICK_SUPERVISOR_INTERVAL = int(os.getenv("MARKET_TICK_SUPERVISOR_INTERVAL", "30"))
MARKET_TICK_SUBSCRIBER_BATCH_SIZE = int(os.getenv("MARKET_TICK_SUBSCRIBER_BATCH_SIZE", "200"))
MARKET_TICK_SUBSCRIBER_FLUSH_INTERVAL = int(os.getenv("MARKET_TICK_SUBSCRIBER_FLUSH_INTERVAL", "2"))


# =============================================================================
# Market Backtest Tick Pub/Sub
# =============================================================================

# Per-request channel is: f"{MARKET_BACKTEST_TICK_CHANNEL_PREFIX}{request_id}"
MARKET_BACKTEST_TICK_CHANNEL_PREFIX = os.getenv(
    "MARKET_BACKTEST_TICK_CHANNEL_PREFIX",
    "market:backtest:ticks:",
)

# Controls how many rows Django fetches from DB per chunk during publishing.


MARKET_BACKTEST_PUBLISH_BATCH_SIZE = int(os.getenv("MARKET_BACKTEST_PUBLISH_BATCH_SIZE", "1000"))


# Django REST Framework Configuration
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK, SPECTACULAR_SETTINGS = build_rest_settings(debug=DEBUG, version=get_version())


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Custom User Model
# https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#substituting-a-custom-user-model

AUTH_USER_MODEL = "accounts.User"


# =============================================================================
# Logging Configuration
# =============================================================================

globals().update(build_logging_settings(BASE_DIR))


# =============================================================================
# Security Settings
# =============================================================================
# https://docs.djangoproject.com/en/5.2/topics/security/

globals().update(build_security_settings(debug=DEBUG))


# =============================================================================
# JWT Configuration
# =============================================================================

JWT_SECRET_KEY = _secret_settings["JWT_SECRET_KEY"]
JWT_ALGORITHM = _secret_settings["JWT_ALGORITHM"]
JWT_EXPIRATION_DELTA = JWT_EXPIRATION
OANDA_TOKEN_ENCRYPTION_KEY = _secret_settings["OANDA_TOKEN_ENCRYPTION_KEY"]
OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS = _secret_settings["OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS"]
REFRESH_TOKEN_EXPIRATION = _secret_settings["REFRESH_TOKEN_EXPIRATION"]  # 7 days
AUTH_REFRESH_COOKIE_NAME = _secret_settings["AUTH_REFRESH_COOKIE_NAME"]
AUTH_REFRESH_COOKIE_HTTPONLY = _secret_settings["AUTH_REFRESH_COOKIE_HTTPONLY"]
AUTH_REFRESH_COOKIE_SECURE = _secret_settings["AUTH_REFRESH_COOKIE_SECURE"]
AUTH_REFRESH_COOKIE_SAMESITE = _secret_settings["AUTH_REFRESH_COOKIE_SAMESITE"]
AUTH_REFRESH_COOKIE_PATH = _secret_settings["AUTH_REFRESH_COOKIE_PATH"]
AUTH_REFRESH_COOKIE_DOMAIN = _secret_settings["AUTH_REFRESH_COOKIE_DOMAIN"]
AUTH_REFRESH_COOKIE_MAX_AGE = _secret_settings["AUTH_REFRESH_COOKIE_MAX_AGE"]


# =============================================================================
# Frontend Configuration
# =============================================================================

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


# =============================================================================
# OANDA API Configuration
# =============================================================================

OANDA_PRACTICE_API = os.getenv("OANDA_PRACTICE_API", "https://api-fxpractice.oanda.com")
OANDA_LIVE_API = os.getenv("OANDA_LIVE_API", "https://api-fxtrade.oanda.com")
OANDA_STREAM_TIMEOUT = int(os.getenv("OANDA_STREAM_TIMEOUT", "30"))
