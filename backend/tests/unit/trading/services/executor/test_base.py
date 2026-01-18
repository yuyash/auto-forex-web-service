"""Unit tests for base executor."""


class TestBaseExecutor:
    """Test base executor."""

    def test_base_executor_module_exists(self):
        """Test base executor module exists."""
        from apps.trading.services.executor import base

        assert base is not None

    def test_base_executor_has_classes(self):
        """Test base executor module has classes."""
        import inspect

        from apps.trading.services.executor import base

        classes = [
            name
            for name, obj in inspect.getmembers(base)
            if inspect.isclass(obj) and obj.__module__ == base.__name__
        ]

        assert len(classes) > 0
