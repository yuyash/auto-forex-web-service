"""Unit tests for trading events base."""


class TestEventsBase:
    """Test events base module."""

    def test_events_base_module_exists(self):
        """Test events base module exists."""
        from apps.trading.events import base

        assert base is not None

    def test_events_base_has_classes(self):
        """Test events base module has classes."""
        import inspect

        from apps.trading.events import base

        classes = [
            name
            for name, obj in inspect.getmembers(base)
            if inspect.isclass(obj) and obj.__module__ == base.__name__
        ]

        assert len(classes) > 0
