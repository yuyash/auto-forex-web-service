"""Unit tests for lock service."""


class TestLockService:
    """Test lock service."""

    def test_lock_module_exists(self):
        """Test lock module exists."""
        from apps.trading.services import lock

        assert lock is not None

    def test_lock_has_classes(self):
        """Test lock module has classes."""
        import inspect

        from apps.trading.services import lock

        classes = [
            name
            for name, obj in inspect.getmembers(lock)
            if inspect.isclass(obj) and obj.__module__ == lock.__name__
        ]

        assert len(classes) > 0
