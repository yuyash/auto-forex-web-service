"""Unit tests for floor models."""


class TestFloorModels:
    """Test floor models."""

    def test_models_module_exists(self):
        """Test models module exists."""
        from apps.trading.strategies.floor import models

        assert models is not None

    def test_models_has_classes(self):
        """Test models module has classes."""
        import inspect

        from apps.trading.strategies.floor import models

        classes = [
            name
            for name, obj in inspect.getmembers(models)
            if inspect.isclass(obj) and obj.__module__ == models.__name__
        ]

        assert len(classes) > 0
