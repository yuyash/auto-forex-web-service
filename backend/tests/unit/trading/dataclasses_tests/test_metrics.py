"""Unit tests for trading metrics dataclasses."""


class TestMetricsDataclasses:
    """Test metrics dataclasses."""

    def test_metrics_module_exists(self):
        """Test metrics module exists."""
        from apps.trading.dataclasses import metrics

        assert metrics is not None

    def test_metrics_has_dataclasses(self):
        """Test metrics module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import metrics

        classes = [
            name
            for name, obj in inspect.getmembers(metrics)
            if inspect.isclass(obj) and obj.__module__ == metrics.__name__
        ]

        assert len(classes) > 0
