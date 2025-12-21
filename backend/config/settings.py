"""
Django settings for auto_forex project.

Auto Forex Trader Backend Configuration

Configuration is done via environment variables and this settings file.
- .env file: Secrets (passwords, keys, credentials)
- Environment variables: Configuration overrides
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file in project root.
# override=True ensures .env values take precedence over shell environment variables.
load_dotenv(BASE_DIR.parent / ".env", override=True)

# =============================================================================
# Server Configuration
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-*6sf5x8=a0@4y+y1wwckk&vlp+)nv5%gl+-az@tt*ahkx3zav0",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

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
    "rest_framework",
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
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Custom security and logging middleware
    "apps.accounts.middleware.HTTPAccessLoggingMiddleware",
    "apps.accounts.middleware.SecurityMonitoringMiddleware",
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
JWT_EXPIRATION = int(os.getenv("JWT_EXPIRATION", "86400"))  # 24 hours
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

CELERY_BROKER_URL = REDIS_URL.replace(f"/{REDIS_DB}", "/2")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True


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


# =============================================================================
# Trading Strategy Defaults
# =============================================================================

# Centralized defaults for Floor Strategy.
# Strategy configs (StrategyConfig.parameters) can override any of these.
TRADING_FLOOR_STRATEGY_DEFAULTS = {
    "instrument": os.getenv("TRADING_FLOOR_INSTRUMENT", "USD_JPY"),
    "base_lot_size": float(os.getenv("TRADING_FLOOR_BASE_LOT_SIZE", "1.0")),
    "retracement_lot_mode": os.getenv("TRADING_FLOOR_RETRACEMENT_LOT_MODE", "additive"),
    "retracement_lot_amount": float(os.getenv("TRADING_FLOOR_RETRACEMENT_LOT_AMOUNT", "1.0")),
    "retracement_pips": float(os.getenv("TRADING_FLOOR_RETRACEMENT_PIPS", "30")),
    "take_profit_pips": float(os.getenv("TRADING_FLOOR_TAKE_PROFIT_PIPS", "25")),
    "max_layers": int(os.getenv("TRADING_FLOOR_MAX_LAYERS", "3")),
    "max_retracements_per_layer": int(os.getenv("TRADING_FLOOR_MAX_RETRACEMENTS_PER_LAYER", "10")),
    "volatility_lock_multiplier": float(
        os.getenv("TRADING_FLOOR_VOLATILITY_LOCK_MULTIPLIER", "5.0")
    ),
    "retracement_trigger_progression": os.getenv(
        "TRADING_FLOOR_RETRACEMENT_TRIGGER_PROGRESSION", "additive"
    ),
    "retracement_trigger_increment": float(
        os.getenv("TRADING_FLOOR_RETRACEMENT_TRIGGER_INCREMENT", "5")
    ),
    "lot_size_progression": os.getenv("TRADING_FLOOR_LOT_SIZE_PROGRESSION", "additive"),
    "lot_size_increment": float(os.getenv("TRADING_FLOOR_LOT_SIZE_INCREMENT", "0.5")),
    "entry_signal_lookback_ticks": int(
        os.getenv("TRADING_FLOOR_ENTRY_SIGNAL_LOOKBACK_TICKS", "10")
    ),
    "direction_method": os.getenv("TRADING_FLOOR_DIRECTION_METHOD", "momentum"),
    "sma_fast_period": int(os.getenv("TRADING_FLOOR_SMA_FAST_PERIOD", "10")),
    "sma_slow_period": int(os.getenv("TRADING_FLOOR_SMA_SLOW_PERIOD", "30")),
    "ema_fast_period": int(os.getenv("TRADING_FLOOR_EMA_FAST_PERIOD", "12")),
    "ema_slow_period": int(os.getenv("TRADING_FLOOR_EMA_SLOW_PERIOD", "26")),
    "rsi_period": int(os.getenv("TRADING_FLOOR_RSI_PERIOD", "14")),
    "rsi_overbought": int(os.getenv("TRADING_FLOOR_RSI_OVERBOUGHT", "70")),
    "rsi_oversold": int(os.getenv("TRADING_FLOOR_RSI_OVERSOLD", "30")),
}
MARKET_BACKTEST_PUBLISH_BATCH_SIZE = int(os.getenv("MARKET_BACKTEST_PUBLISH_BATCH_SIZE", "1000"))


# Django REST Framework Configuration
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%fZ",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",
}


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

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/django.log")
LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

LOG_FILE_PATH = BASE_DIR / LOG_FILE
LOG_FILE_HANDLER: dict[str, Any] = {
    "level": LOG_LEVEL,
    "class": "logging.NullHandler",
}

if os.getenv("DJANGO_ENABLE_FILE_LOGGING", "True") == "True":
    try:
        LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE_PATH, "a", encoding="utf-8"):
            pass
        LOG_FILE_HANDLER = {
            "level": LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE_PATH,
            "maxBytes": LOG_MAX_SIZE,
            "backupCount": LOG_BACKUP_COUNT,
            "formatter": "verbose",
        }
    except OSError:
        # Fall back to console-only logging when file access is restricted
        LOG_FILE_HANDLER = {
            "level": "INFO",
            "class": "logging.NullHandler",
        }

CELERY_MARKET_LOG_FILE = os.getenv("CELERY_MARKET_LOG_FILE", "logs/celery_market.log")
CELERY_TRADING_LOG_FILE = os.getenv("CELERY_TRADING_LOG_FILE", "logs/celery_trading.log")

CELERY_MARKET_LOG_PATH = BASE_DIR / CELERY_MARKET_LOG_FILE
CELERY_TRADING_LOG_PATH = BASE_DIR / CELERY_TRADING_LOG_FILE

CELERY_MARKET_FILE_HANDLER: dict[str, Any] = {
    "level": LOG_LEVEL,
    "class": "logging.NullHandler",
}

CELERY_TRADING_FILE_HANDLER: dict[str, Any] = {
    "level": LOG_LEVEL,
    "class": "logging.NullHandler",
}


def _celery_rotating_file_handler(path: Path) -> dict[str, Any]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8"):
            pass
        return {
            "level": LOG_LEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": path,
            "maxBytes": LOG_MAX_SIZE,
            "backupCount": LOG_BACKUP_COUNT,
            "formatter": "celery_task",
        }
    except OSError:
        return {
            "level": "INFO",
            "class": "logging.NullHandler",
        }


if os.getenv("DJANGO_ENABLE_FILE_LOGGING", "True") == "True":
    CELERY_MARKET_FILE_HANDLER = _celery_rotating_file_handler(CELERY_MARKET_LOG_PATH)
    CELERY_TRADING_FILE_HANDLER = _celery_rotating_file_handler(CELERY_TRADING_LOG_PATH)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "celery_task": {
            "format": "{asctime} {levelname} {name} {pathname}:{lineno} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{asctime} {levelname} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": LOG_FILE_HANDLER,
        "celery_market_file": CELERY_MARKET_FILE_HANDLER,
        "celery_trading_file": CELERY_TRADING_FILE_HANDLER,
    },
    "root": {
        "handlers": ["console", "file"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # Django can emit very noisy DEBUG stack traces from template variable resolution
        # (e.g. the technical 404 page iterating URL resolver structures). Keep these
        # at INFO+ even when LOG_LEVEL=DEBUG so real application logs remain readable.
        "django.template": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.template.base": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # Per-app Celery task logs (also propagate to root)
        "apps.market.tasks": {
            "handlers": ["celery_market_file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "apps.market.services.oanda": {
            "handlers": ["celery_market_file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "apps.market.services.task": {
            "handlers": ["celery_market_file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "apps.trading.tasks": {
            "handlers": ["celery_trading_file"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "channels": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # Avoid noisy cancellation traces from asyncio when clients disconnect
        # or requests are cancelled (common during local dev with hot reload).
        "asyncio": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


# =============================================================================
# Security Settings
# =============================================================================
# https://docs.djangoproject.com/en/5.2/topics/security/

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True


# =============================================================================
# CORS Configuration
# =============================================================================

CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
CORS_ALLOW_CREDENTIALS = True


# =============================================================================
# JWT Configuration
# =============================================================================

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DELTA = JWT_EXPIRATION


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
