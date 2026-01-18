"""Unit tests for view helpers."""


class TestViewHelpers:
    """Test view helper functions."""

    def test_helpers_module_exists(self):
        """Test helpers module exists."""
        from apps.trading.views import _helpers

        assert _helpers is not None

    def test_helpers_has_functions(self):
        """Test helpers module has functions."""
        import inspect

        from apps.trading.views import _helpers

        functions = [
            name
            for name, obj in inspect.getmembers(_helpers)
            if inspect.isfunction(obj) and obj.__module__ == _helpers.__name__
        ]

        assert len(functions) > 0
