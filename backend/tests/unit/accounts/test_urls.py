"""Unit tests for accounts URLs."""


class TestAccountsURLs:
    """Test accounts URL configuration."""

    def test_urls_module_exists(self):
        """Test accounts urls module exists."""
        from apps.accounts import urls

        assert urls is not None
        assert hasattr(urls, "urlpatterns")

    def test_app_name_is_set(self):
        """Test app_name is configured."""
        from apps.accounts import urls

        assert hasattr(urls, "app_name")
        assert urls.app_name == "accounts"
