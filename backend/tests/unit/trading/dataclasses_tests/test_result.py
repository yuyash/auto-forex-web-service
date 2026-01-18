"""Unit tests for trading result dataclasses."""


class TestResultDataclasses:
    """Test result dataclasses."""

    def test_result_module_exists(self):
        """Test result module exists."""
        from apps.trading.dataclasses import result

        assert result is not None

    def test_result_has_dataclasses(self):
        """Test result module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import result

        classes = [
            name
            for name, obj in inspect.getmembers(result)
            if inspect.isclass(obj) and obj.__module__ == result.__name__
        ]

        assert len(classes) > 0
