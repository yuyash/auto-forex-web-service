"""Unit tests for tick serializers."""


class TestTickSerializers:
    """Test tick serializers."""

    def test_tick_serializers_module_exists(self):
        """Test tick serializers module exists."""
        from apps.trading.serializers import tick

        assert tick is not None

    def test_tick_serializers_has_classes(self):
        """Test tick serializers module has classes."""
        import inspect

        from apps.trading.serializers import tick

        classes = [
            name
            for name, obj in inspect.getmembers(tick)
            if inspect.isclass(obj) and obj.__module__ == tick.__name__
        ]

        assert len(classes) > 0
