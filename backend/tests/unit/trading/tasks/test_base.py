"""Unit tests for base tasks."""


class TestBaseTasks:
    """Test base tasks module."""

    def test_base_tasks_module_exists(self):
        """Test base tasks module exists."""
        from apps.trading.tasks import base

        assert base is not None

    def test_base_tasks_has_classes(self):
        """Test base tasks module has classes."""
        import inspect

        from apps.trading.tasks import base

        classes = [
            name
            for name, obj in inspect.getmembers(base)
            if inspect.isclass(obj) and obj.__module__ == base.__name__
        ]

        assert len(classes) > 0
