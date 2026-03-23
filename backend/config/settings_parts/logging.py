"""Logging settings helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def build_logging_settings(base_dir: Path) -> dict[str, Any]:
    """Build logging configuration and companion log-file settings."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/django.log")
    log_max_size = int(os.getenv("LOG_MAX_SIZE", "10485760"))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    enable_file_logging = os.getenv("DJANGO_ENABLE_FILE_LOGGING", "True") == "True"

    log_file_path = base_dir / log_file
    log_file_handler: dict[str, Any] = {
        "level": log_level,
        "class": "logging.NullHandler",
    }

    if enable_file_logging:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file_path, "a", encoding="utf-8"):
                pass
            log_file_handler = {
                "level": log_level,
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path,
                "maxBytes": log_max_size,
                "backupCount": log_backup_count,
                "formatter": "verbose",
            }
        except OSError:
            log_file_handler = {
                "level": "INFO",
                "class": "logging.NullHandler",
            }

    celery_market_log_file = os.getenv("CELERY_MARKET_LOG_FILE", "logs/celery_market.log")
    celery_trading_log_file = os.getenv("CELERY_TRADING_LOG_FILE", "logs/celery_trading.log")
    celery_market_log_path = base_dir / celery_market_log_file
    celery_trading_log_path = base_dir / celery_trading_log_file

    def _celery_rotating_file_handler(path: Path) -> dict[str, Any]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8"):
                pass
            return {
                "level": log_level,
                "class": "logging.handlers.RotatingFileHandler",
                "filename": path,
                "maxBytes": log_max_size,
                "backupCount": log_backup_count,
                "formatter": "celery_task",
            }
        except OSError:
            return {
                "level": "INFO",
                "class": "logging.NullHandler",
            }

    celery_market_file_handler: dict[str, Any] = {
        "level": log_level,
        "class": "logging.NullHandler",
    }
    celery_trading_file_handler: dict[str, Any] = {
        "level": log_level,
        "class": "logging.NullHandler",
    }

    if enable_file_logging:
        celery_market_file_handler = _celery_rotating_file_handler(celery_market_log_path)
        celery_trading_file_handler = _celery_rotating_file_handler(celery_trading_log_path)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{asctime} {levelname:<8s} {name:<40s} {message}",
                "style": "{",
            },
            "celery_task": {
                "format": "{asctime} {levelname:<8s} {name:<40s} {pathname}:{lineno} {message}",
                "style": "{",
            },
            "simple": {
                "format": "{asctime} {levelname:<8s} {message}",
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
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "file": log_file_handler,
            "celery_market_file": celery_market_file_handler,
            "celery_trading_file": celery_trading_file_handler,
        },
        "root": {
            "handlers": ["console", "file"],
            "level": log_level,
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
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
                "level": log_level,
                "propagate": False,
            },
            "apps.market.tasks": {
                "handlers": ["celery_market_file"],
                "level": log_level,
                "propagate": True,
            },
            "apps.market.services.oanda": {
                "handlers": ["celery_market_file"],
                "level": log_level,
                "propagate": True,
            },
            "apps.market.services.celery": {
                "handlers": ["celery_market_file"],
                "level": log_level,
                "propagate": True,
            },
            "apps.trading.tasks": {
                "handlers": ["celery_trading_file"],
                "level": log_level,
                "propagate": True,
            },
            "channels": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "apps.accounts.middlewares.logging": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "asyncio": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    return {
        "LOG_LEVEL": log_level,
        "LOG_FILE": log_file,
        "LOG_MAX_SIZE": log_max_size,
        "LOG_BACKUP_COUNT": log_backup_count,
        "LOGGING": logging_config,
    }
