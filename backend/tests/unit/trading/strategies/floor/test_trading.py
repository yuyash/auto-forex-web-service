"""Unit tests for floor trading."""


class TestFloorTrading:
    """Test floor trading."""

    def test_trading_module_exists(self):
        """Test trading module exists."""
        from apps.trading.strategies.floor import trading

        assert trading is not None

    def test_trading_has_classes(self):
        """Test trading module has classes."""
        import inspect

        from apps.trading.strategies.floor import trading

        classes = [
            name
            for name, obj in inspect.getmembers(trading)
            if inspect.isclass(obj) and obj.__module__ == trading.__name__
        ]

        assert len(classes) > 0
