"""Unit tests for floor event."""


class TestFloorEvent:
    """Test floor event."""

    def test_event_module_exists(self):
        """Test event module exists."""
        from apps.trading.strategies.floor import event

        assert event is not None

    def test_event_has_classes(self):
        """Test event module has classes."""
        import inspect

        from apps.trading.strategies.floor import event

        classes = [
            name
            for name, obj in inspect.getmembers(event)
            if inspect.isclass(obj) and obj.__module__ == event.__name__
        ]

        assert len(classes) > 0
