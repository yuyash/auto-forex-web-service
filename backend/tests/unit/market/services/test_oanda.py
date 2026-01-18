"""Unit tests for OANDA service."""


class TestOandaService:
    """Test OANDA service."""

    def test_oanda_service_module_exists(self):
        """Test OANDA service module exists."""
        from apps.market.services import oanda

        assert oanda is not None

    def test_oanda_service_has_classes(self):
        """Test OANDA service has classes."""
        import inspect

        from apps.market.services import oanda

        classes = [
            name
            for name, obj in inspect.getmembers(oanda)
            if inspect.isclass(obj) and obj.__module__ == oanda.__name__
        ]

        # Should have service classes
        assert len(classes) > 0
