"""Unit tests for market views."""


class TestMarketViews:
    """Test market views module."""

    def test_views_module_exists(self):
        """Test market views module exists."""
        from apps.market import views

        assert views is not None

    def test_views_module_has_classes(self):
        """Test views module has view classes."""
        import inspect

        from apps.market import views

        # Get all classes in the module
        classes = [
            name
            for name, obj in inspect.getmembers(views)
            if inspect.isclass(obj) and obj.__module__ == views.__name__
        ]

        # Should have view classes
        assert len(classes) > 0
