"""Test settings - uses SQLite in-memory database for fast unit tests."""

import copy
import sys
from typing import MutableMapping

from .settings import LOGGING as BASE_LOGGING
from .settings import *  # noqa: F401,F403 pylint: disable=wildcard-import,unused-wildcard-import

# Use SQLite in-memory database for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


class DisableMigrations:
    """Helper class to disable migrations during tests for better performance."""

    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str) -> None:
        return None


# Disable migrations for faster tests
MIGRATION_MODULES = DisableMigrations()

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Use local memory cache for tests (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Use in-memory channel layer for tests to avoid Redis dependency
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        "CONFIG": {
            "capacity": 1500,
            "expiry": 10,
        },
    }
}

_LOGGING_COPY = copy.deepcopy(BASE_LOGGING)
handlers_mapping = _LOGGING_COPY.get("handlers", {})
if not isinstance(handlers_mapping, MutableMapping):
    handlers_mapping = {}
handlers = dict(handlers_mapping)
handlers["file"] = {
    "level": "INFO",
    "class": "logging.StreamHandler",
    "formatter": "verbose",
    "stream": sys.stdout,
}
_LOGGING_COPY["handlers"] = handlers
LOGGING = _LOGGING_COPY
