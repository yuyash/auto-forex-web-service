"""Unit tests for metrics serializers."""


class TestMetricsSerializers:
    """Test metrics serializers."""

    def test_metrics_serializers_module_exists(self):
        """Test metrics serializers module exists."""
        from apps.trading.serializers import metrics

        assert metrics is not None

    def test_metrics_serializers_has_classes(self):
        """Test metrics serializers module has classes."""
        import inspect

        from apps.trading.serializers import metrics

        classes = [
            name
            for name, obj in inspect.getmembers(metrics)
            if inspect.isclass(obj) and obj.__module__ == metrics.__name__
        ]

        assert len(classes) > 0
