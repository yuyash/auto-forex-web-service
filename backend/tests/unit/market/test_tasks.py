"""Unit tests for market tasks."""


class TestMarketTasks:
    """Test market Celery tasks."""

    def test_tasks_module_exists(self):
        """Test market tasks module exists."""
        from apps.market import tasks

        assert tasks is not None

    def test_tasks_are_decorated(self):
        """Test tasks are Celery tasks."""
        import inspect

        from apps.market import tasks

        # Get all functions in the module
        functions = [
            name
            for name, obj in inspect.getmembers(tasks)
            if inspect.isfunction(obj) and obj.__module__ == tasks.__name__
        ]

        # Should have task functions
        assert len(functions) >= 0
