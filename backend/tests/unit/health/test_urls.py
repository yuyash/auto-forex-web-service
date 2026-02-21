"""Unit tests for health URLs."""

from django.urls import reverse


class TestHealthURLs:
    """Test health URL configuration."""

    def test_urls_module_exists(self):
        """Test health urls module exists."""
        from apps.health import urls

        assert urls is not None
        assert hasattr(urls, "urlpatterns")

    def test_app_name_is_set(self):
        """Test app_name is configured."""
        from apps.health import urls

        assert hasattr(urls, "app_name")
        assert urls.app_name == "health"

    def test_health_check_url_resolves(self):
        """Test health check URL resolves."""
        url = reverse("health:health_check")
        assert url is not None
        assert "/health" in url or "/api/health" in url
