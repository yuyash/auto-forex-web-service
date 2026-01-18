"""Unit tests for floor calculators."""


class TestFloorCalculators:
    """Test floor calculators."""

    def test_calculators_module_exists(self):
        """Test calculators module exists."""
        from apps.trading.strategies.floor import calculators

        assert calculators is not None

    def test_calculators_has_classes_or_functions(self):
        """Test calculators module has classes or functions."""
        import inspect

        from apps.trading.strategies.floor import calculators

        members = inspect.getmembers(calculators)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
