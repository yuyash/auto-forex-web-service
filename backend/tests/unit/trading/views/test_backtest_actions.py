"""Unit tests for backtest actions views."""


class TestBacktestActionsViews:
    """Test backtest actions views."""

    def test_backtest_actions_module_exists(self):
        """Test backtest actions module exists."""
        from apps.trading.views import backtest_actions

        assert backtest_actions is not None

    def test_backtest_actions_has_view_classes(self):
        """Test backtest actions module has view classes."""
        import inspect

        from apps.trading.views import backtest_actions

        classes = [
            name
            for name, obj in inspect.getmembers(backtest_actions)
            if inspect.isclass(obj) and obj.__module__ == backtest_actions.__name__
        ]

        assert len(classes) > 0
