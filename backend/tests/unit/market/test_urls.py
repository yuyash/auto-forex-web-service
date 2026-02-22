"""Unit tests for market URLs."""


class TestMarketURLs:
    """Test market URL configuration."""

    def test_urls_module_exists(self):
        """Test market urls module exists."""
        from apps.market import urls

        assert urls is not None
        assert hasattr(urls, "urlpatterns")

    def test_app_name_is_set(self):
        """Test app_name is configured."""
        from apps.market import urls

        assert hasattr(urls, "app_name")
        assert urls.app_name == "market"
