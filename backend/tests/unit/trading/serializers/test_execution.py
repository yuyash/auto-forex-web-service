"""Unit tests for execution serializers."""


class TestExecutionSerializers:
    """Test execution serializers."""

    def test_execution_serializers_module_exists(self):
        """Test execution serializers module exists."""
        from apps.trading.serializers import execution

        assert execution is not None

    def test_execution_serializers_has_classes(self):
        """Test execution serializers module has classes."""
        import inspect

        from apps.trading.serializers import execution

        classes = [
            name
            for name, obj in inspect.getmembers(execution)
            if inspect.isclass(obj) and obj.__module__ == execution.__name__
        ]

        assert len(classes) > 0
