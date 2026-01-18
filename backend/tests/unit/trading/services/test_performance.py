"""Unit tests for performance service."""


class TestPerformanceService:
    """Test performance service."""

    def test_performance_module_exists(self):
        """Test performance module exists."""
        from apps.trading.services import performance

        assert performance is not None

    def test_performance_has_classes_or_functions(self):
        """Test performance module has classes or functions."""
        import inspect

        from apps.trading.services import performance

        members = inspect.getmembers(performance)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
