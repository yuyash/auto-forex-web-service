"""Unit tests for trading dataclasses context."""

from unittest.mock import MagicMock
from uuid import uuid4

from apps.trading.dataclasses.context import EventContext


class TestEventContext:
    """Test EventContext dataclass."""

    def test_creation(self):
        user = MagicMock()
        account = MagicMock()
        task_id = uuid4()
        ctx = EventContext(
            user=user,
            account=account,
            instrument="USD_JPY",
            task_id=task_id,
            task_type="trading",
        )
        assert ctx.user is user
        assert ctx.account is account
        assert ctx.instrument == "USD_JPY"
        assert ctx.task_id == task_id

    def test_account_can_be_none(self):
        """For backtests, account is None."""
        ctx = EventContext(
            user=MagicMock(),
            account=None,
            instrument="EUR_USD",
            task_id=uuid4(),
            task_type="backtest",
        )
        assert ctx.account is None
