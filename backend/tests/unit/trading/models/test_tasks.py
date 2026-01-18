"""Unit tests for tasks models."""


class TestTasksModels:
    """Test tasks models module."""

    def test_tasks_models_module_exists(self):
        """Test tasks models module exists."""
        from apps.trading.models import tasks

        assert tasks is not None

    def test_tasks_models_has_classes(self):
        """Test tasks models module has model classes."""
        import inspect

        from apps.trading.models import tasks

        classes = [
            name
            for name, obj in inspect.getmembers(tasks)
            if inspect.isclass(obj) and obj.__module__ == tasks.__name__
        ]

        assert len(classes) > 0
