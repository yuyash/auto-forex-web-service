"""Unit tests for validation service."""


class TestValidationService:
    """Test validation service."""

    def test_validation_module_exists(self):
        """Test validation module exists."""
        from apps.trading.services import validation

        assert validation is not None

    def test_validation_has_classes_or_functions(self):
        """Test validation module has classes or functions."""
        import inspect

        from apps.trading.services import validation

        members = inspect.getmembers(validation)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
