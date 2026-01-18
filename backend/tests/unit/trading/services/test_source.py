"""Unit tests for data source service."""


class TestDataSourceService:
    """Test data source service."""

    def test_source_module_exists(self):
        """Test source module exists."""
        from apps.trading.services import source

        assert source is not None

    def test_source_has_classes(self):
        """Test source module has classes."""
        import inspect

        from apps.trading.services import source

        classes = [
            name
            for name, obj in inspect.getmembers(source)
            if inspect.isclass(obj) and obj.__module__ == source.__name__
        ]

        assert len(classes) > 0
