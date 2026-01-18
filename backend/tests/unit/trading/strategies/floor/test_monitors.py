"""Unit tests for floor monitors."""


class TestFloorMonitors:
    """Test floor monitors."""

    def test_monitors_module_exists(self):
        """Test monitors module exists."""
        from apps.trading.strategies.floor import monitors

        assert monitors is not None

    def test_monitors_has_classes(self):
        """Test monitors module has classes."""
        import inspect

        from apps.trading.strategies.floor import monitors

        classes = [
            name
            for name, obj in inspect.getmembers(monitors)
            if inspect.isclass(obj) and obj.__module__ == monitors.__name__
        ]

        assert len(classes) > 0
