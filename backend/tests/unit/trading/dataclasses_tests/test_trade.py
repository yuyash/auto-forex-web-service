"""Unit tests for trade dataclasses."""


class TestTradeDataclasses:
    """Test trade dataclasses."""

    def test_trade_module_exists(self):
        """Test trade module exists."""
        from apps.trading.dataclasses import trade

        assert trade is not None

    def test_trade_has_dataclasses(self):
        """Test trade module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import trade

        classes = [
            name
            for name, obj in inspect.getmembers(trade)
            if inspect.isclass(obj) and obj.__module__ == trade.__name__
        ]

        assert len(classes) > 0
