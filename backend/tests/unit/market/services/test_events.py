"""Unit tests for market events service."""


class TestMarketEventService:
    """Test market event service."""

    def test_event_service_module_exists(self):
        """Test event service module exists."""
        from apps.market.services import events

        assert events is not None

    def test_event_service_has_classes_or_functions(self):
        """Test event service has classes or functions."""
        import inspect

        from apps.market.services import events

        members = inspect.getmembers(events)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
