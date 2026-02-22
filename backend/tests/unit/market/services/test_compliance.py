"""Unit tests for market compliance service."""


class TestComplianceService:
    """Test compliance service."""

    def test_compliance_service_module_exists(self):
        """Test compliance service module exists."""
        from apps.market.services import compliance

        assert compliance is not None

    def test_compliance_service_has_classes_or_functions(self):
        """Test compliance service has classes or functions."""
        import inspect

        from apps.market.services import compliance

        members = inspect.getmembers(compliance)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        # Should have at least some classes or functions
        assert len(classes) + len(functions) > 0
