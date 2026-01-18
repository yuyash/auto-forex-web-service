"""Unit tests for floor components."""


class TestFloorComponents:
    """Test floor components."""

    def test_components_module_exists(self):
        """Test components module exists."""
        from apps.trading.strategies.floor import components

        assert components is not None

    def test_components_has_classes(self):
        """Test components module has classes."""
        import inspect

        from apps.trading.strategies.floor import components

        classes = [
            name
            for name, obj in inspect.getmembers(components)
            if inspect.isclass(obj) and obj.__module__ == components.__name__
        ]

        assert len(classes) > 0
