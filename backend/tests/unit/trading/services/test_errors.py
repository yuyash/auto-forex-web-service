"""Unit tests for trading errors."""


class TestTradingErrors:
    """Test trading error classes."""

    def test_errors_module_exists(self):
        """Test errors module exists."""
        from apps.trading.services import errors

        assert errors is not None

    def test_errors_has_exception_classes(self):
        """Test errors module has exception classes."""
        import inspect

        from apps.trading.services import errors

        classes = [
            name
            for name, obj in inspect.getmembers(errors)
            if inspect.isclass(obj) and issubclass(obj, Exception)
        ]

        assert len(classes) > 0
