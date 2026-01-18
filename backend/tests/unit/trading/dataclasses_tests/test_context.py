"""Unit tests for trading context dataclasses."""


class TestContextDataclasses:
    """Test context dataclasses."""

    def test_context_module_exists(self):
        """Test context module exists."""
        from apps.trading.dataclasses import context

        assert context is not None

    def test_context_has_dataclasses(self):
        """Test context module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import context

        classes = [
            name
            for name, obj in inspect.getmembers(context)
            if inspect.isclass(obj) and obj.__module__ == context.__name__
        ]

        assert len(classes) > 0
