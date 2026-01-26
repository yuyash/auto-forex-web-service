"""Unit tests for trading context dataclasses."""

from uuid import uuid4

from apps.trading.dataclasses.context import EventContext
from apps.trading.enums import TaskType


class TestContextDataclasses:
    """Test context dataclasses."""

    def test_context_module_exists(self):
        """Test context module exists."""
        from apps.trading.dataclasses import context

        assert context is not None

    def test_context_has_dataclasses(self):
        """Test context module has dataclasses."""
        import inspect

        from apps.trading.dataclasses import context

        classes = [
            name
            for name, obj in inspect.getmembers(context)
            if inspect.isclass(obj) and obj.__module__ == context.__name__
        ]

        assert len(classes) > 0

    def test_event_context_has_required_fields(self):
        """Test that EventContext has all required fields."""
        from dataclasses import fields

        field_names = {f.name for f in fields(EventContext)}

        required_fields = {"user", "account", "instrument", "task_id", "task_type"}
        assert required_fields.issubset(field_names), (
            f"Missing fields: {required_fields - field_names}"
        )

    def test_event_context_can_be_created(self):
        """Test that EventContext can be instantiated with all fields."""
        from unittest.mock import Mock

        mock_user = Mock()
        mock_account = Mock()
        task_id = uuid4()

        context = EventContext(
            user=mock_user,
            account=mock_account,
            instrument="USD_JPY",
            task_id=task_id,
            task_type=TaskType.BACKTEST,
        )

        assert context.user == mock_user
        assert context.account == mock_account
        assert context.instrument == "USD_JPY"
        assert context.task_id == task_id
        assert context.task_type == TaskType.BACKTEST

    def test_event_context_account_can_be_none(self):
        """Test that EventContext account can be None (for backtests)."""
        from unittest.mock import Mock

        mock_user = Mock()
        task_id = uuid4()

        context = EventContext(
            user=mock_user,
            account=None,
            instrument="USD_JPY",
            task_id=task_id,
            task_type=TaskType.BACKTEST,
        )

        assert context.account is None
