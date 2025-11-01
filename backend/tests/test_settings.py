"""
Test Django settings configuration.

This test verifies that the Django settings are properly configured.
"""

from django.conf import settings

import pytest


@pytest.mark.unit
def test_django_settings_loaded() -> None:
    """Test that Django settings are loaded correctly."""
    assert settings.configured
    assert settings.SECRET_KEY is not None


@pytest.mark.unit
def test_installed_apps_configured() -> None:
    """Test that required apps are installed."""
    required_apps = [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "rest_framework",
        "channels",
        "daphne",
    ]
    for app in required_apps:
        assert app in settings.INSTALLED_APPS


@pytest.mark.unit
def test_database_configured() -> None:
    """Test that database is configured."""
    assert "default" in settings.DATABASES
    # Test settings use SQLite for speed, production uses PostgreSQL
    assert settings.DATABASES["default"]["ENGINE"] in [
        "django.db.backends.postgresql",
        "django.db.backends.sqlite3",
    ]


@pytest.mark.unit
def test_celery_configured() -> None:
    """Test that Celery is configured."""
    assert hasattr(settings, "CELERY_BROKER_URL")
    assert hasattr(settings, "CELERY_RESULT_BACKEND")
    assert settings.CELERY_TASK_SERIALIZER == "json"


@pytest.mark.unit
def test_rest_framework_configured() -> None:
    """Test that Django REST Framework is configured."""
    assert hasattr(settings, "REST_FRAMEWORK")
    assert "DEFAULT_AUTHENTICATION_CLASSES" in settings.REST_FRAMEWORK
    assert "DEFAULT_PERMISSION_CLASSES" in settings.REST_FRAMEWORK


@pytest.mark.unit
def test_channels_configured() -> None:
    """Test that Django Channels is configured."""
    assert hasattr(settings, "CHANNEL_LAYERS")
    assert "default" in settings.CHANNEL_LAYERS
    assert settings.ASGI_APPLICATION == "trading_system.asgi.application"
