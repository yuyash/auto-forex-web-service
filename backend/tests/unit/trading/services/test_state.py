"""Unit tests for state service."""


class TestStateService:
    """Test state service."""

    def test_state_module_exists(self):
        """Test state module exists."""
        from apps.trading.services import state

        assert state is not None

    def test_state_has_classes_or_functions(self):
        """Test state module has classes or functions."""
        import inspect

        from apps.trading.services import state

        members = inspect.getmembers(state)
        classes = [m for m in members if inspect.isclass(m[1])]
        functions = [m for m in members if inspect.isfunction(m[1])]

        assert len(classes) + len(functions) > 0
