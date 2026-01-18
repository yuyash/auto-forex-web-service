"""Unit tests for floor strategy."""


class TestFloorStrategy:
    """Test floor strategy."""

    def test_strategy_module_exists(self):
        """Test strategy module exists."""
        from apps.trading.strategies.floor import strategy

        assert strategy is not None

    def test_strategy_has_classes(self):
        """Test strategy module has classes."""
        import inspect

        from apps.trading.strategies.floor import strategy

        classes = [
            name
            for name, obj in inspect.getmembers(strategy)
            if inspect.isclass(obj) and obj.__module__ == strategy.__name__
        ]

        assert len(classes) > 0
