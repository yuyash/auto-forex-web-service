"""
Pytest configuration for backend tests.
"""

import os

import django
from django.conf import settings

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django
django.setup()


def pytest_configure(config):
    """Configure pytest with Django settings."""
    settings.DEBUG = False
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
