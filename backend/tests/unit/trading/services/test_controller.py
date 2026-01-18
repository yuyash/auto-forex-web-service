"""Unit tests for controller service."""


class TestControllerService:
    """Test controller service."""

    def test_controller_module_exists(self):
        """Test controller module exists."""
        from apps.trading.services import controller

        assert controller is not None

    def test_controller_has_classes(self):
        """Test controller module has classes."""
        import inspect

        from apps.trading.services import controller

        classes = [
            name
            for name, obj in inspect.getmembers(controller)
            if inspect.isclass(obj) and obj.__module__ == controller.__name__
        ]

        assert len(classes) > 0
