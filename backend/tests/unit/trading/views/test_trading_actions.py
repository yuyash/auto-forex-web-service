"""Unit tests for trading actions views."""


class TestTradingActionsViews:
    """Test trading actions views."""

    def test_trading_actions_module_exists(self):
        """Test trading actions module exists."""
        from apps.trading.views import trading_actions

        assert trading_actions is not None

    def test_trading_actions_has_view_classes(self):
        """Test trading actions module has view classes."""
        import inspect

        from apps.trading.views import trading_actions

        classes = [
            name
            for name, obj in inspect.getmembers(trading_actions)
            if inspect.isclass(obj) and obj.__module__ == trading_actions.__name__
        ]

        assert len(classes) > 0
