"""Unit tests for strategies views."""


class TestStrategiesViews:
    """Test strategies views."""

    def test_strategies_module_exists(self):
        """Test strategies module exists."""
        from apps.trading.views import strategies

        assert strategies is not None

    def test_strategies_has_view_classes(self):
        """Test strategies module has view classes."""
        import inspect

        from apps.trading.views import strategies

        classes = [
            name
            for name, obj in inspect.getmembers(strategies)
            if inspect.isclass(obj) and obj.__module__ == strategies.__name__
        ]

        assert len(classes) > 0
