"""Test settings - uses SQLite in-memory database for fast unit tests."""

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
