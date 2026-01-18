"""Unit tests for equity service."""


class TestEquityService:
    """Test equity service."""

    def test_equity_module_exists(self):
        """Test equity module exists."""
        from apps.trading.services import equity

        assert equity is not None

    def test_equity_has_classes_or_functions(self):
        """Test equity module has classes or functions."""
        import inspect

        from apps.trading.services import equity

        members = inspect.getmembers(equity)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
