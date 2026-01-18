"""Unit tests for base strategy."""


class TestBaseStrategy:
    """Test base strategy."""

    def test_base_strategy_module_exists(self):
        """Test base strategy module exists."""
        from apps.trading.strategies import base

        assert base is not None

    def test_base_strategy_has_classes(self):
        """Test base strategy module has classes."""
        import inspect

        from apps.trading.strategies import base

        classes = [
            name
            for name, obj in inspect.getmembers(base)
            if inspect.isclass(obj) and obj.__module__ == base.__name__
        ]

        assert len(classes) > 0
