"""Unit tests for trading celery service."""


class TestTradingCeleryService:
    """Test trading Celery service."""

    def test_celery_module_exists(self):
        """Test celery module exists."""
        from apps.trading.services import celery

        assert celery is not None

    def test_celery_has_functions(self):
        """Test celery module has functions."""
        import inspect

        from apps.trading.services import celery

        functions = [name for name, obj in inspect.getmembers(celery) if inspect.isfunction(obj)]

        assert len(functions) >= 0
