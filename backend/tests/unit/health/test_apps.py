"""Unit tests for health apps configuration."""

from django.apps import apps

from apps.health.apps import HealthConfig


class TestHealthConfig:
    """Test HealthConfig."""

    def test_app_name(self):
        """Test app name is correct."""
        assert HealthConfig.name == "apps.health"

    def test_app_is_registered(self):
        """Test health app is registered."""
        app_config = apps.get_app_config("health")
        assert app_config.name == "apps.health"
        assert isinstance(app_config, HealthConfig)

    def test_default_auto_field(self):
        """Test default auto field is configured."""
        assert HealthConfig.default_auto_field == "django.db.models.BigAutoField"
