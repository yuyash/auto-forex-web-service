"""Unit tests for validation dataclasses."""


class TestValidationDataclasses:
    """Test validation dataclasses."""

    def test_validation_module_exists(self):
        """Test validation module exists."""
        from apps.trading.dataclasses import validation

        assert validation is not None

    def test_validation_has_dataclasses(self):
        """Test validation module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import validation

        classes = [
            name
            for name, obj in inspect.getmembers(validation)
            if inspect.isclass(obj) and obj.__module__ == validation.__name__
        ]

        assert len(classes) > 0
