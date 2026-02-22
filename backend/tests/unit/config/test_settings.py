"""Unit tests for Django settings."""

from django.conf import settings


class TestSettings:
    """Test Django settings configuration."""

    def test_debug_setting_exists(self):
        """Test DEBUG setting exists."""
        assert hasattr(settings, "DEBUG")
        assert isinstance(settings.DEBUG, bool)

    def test_secret_key_exists(self):
        """Test SECRET_KEY is configured."""
        assert hasattr(settings, "SECRET_KEY")
        assert len(settings.SECRET_KEY) > 0

    def test_installed_apps_includes_required_apps(self):
        """Test required apps are installed."""
        required_apps = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "rest_framework",
        ]

        for app in required_apps:
            assert app in settings.INSTALLED_APPS

    def test_custom_apps_installed(self):
        """Test custom apps are installed."""
        custom_apps = [
            "apps.accounts",
            "apps.market",
            "apps.trading",
            "apps.health",
        ]

        for app in custom_apps:
            assert app in settings.INSTALLED_APPS

    def test_database_configured(self):
        """Test database is configured."""
        assert hasattr(settings, "DATABASES")
        assert "default" in settings.DATABASES
        assert "ENGINE" in settings.DATABASES["default"]

    def test_jwt_settings_configured(self):
        """Test JWT settings are configured."""
        assert hasattr(settings, "JWT_SECRET_KEY")
        assert hasattr(settings, "JWT_ALGORITHM")
        assert hasattr(settings, "JWT_EXPIRATION_DELTA")

    def test_celery_settings_configured(self):
        """Test Celery settings are configured."""
        assert hasattr(settings, "CELERY_BROKER_URL")
        assert hasattr(settings, "CELERY_RESULT_BACKEND")

    def test_cors_settings_configured(self):
        """Test CORS settings are configured."""
        assert hasattr(settings, "CORS_ALLOWED_ORIGINS") or hasattr(
            settings, "CORS_ALLOW_ALL_ORIGINS"
        )

    def test_rest_framework_configured(self):
        """Test REST framework is configured."""
        assert hasattr(settings, "REST_FRAMEWORK")
        assert isinstance(settings.REST_FRAMEWORK, dict)
