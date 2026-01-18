"""Unit tests for floor history."""


class TestFloorHistory:
    """Test floor history."""

    def test_history_module_exists(self):
        """Test history module exists."""
        from apps.trading.strategies.floor import history

        assert history is not None

    def test_history_has_classes(self):
        """Test history module has classes."""
        import inspect

        from apps.trading.strategies.floor import history

        classes = [
            name
            for name, obj in inspect.getmembers(history)
            if inspect.isclass(obj) and obj.__module__ == history.__name__
        ]

        assert len(classes) > 0
