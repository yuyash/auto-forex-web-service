"""Unit tests for signal handlers."""

from typing import Any
from unittest.mock import patch

import pytest

from apps.market.signals import (
    account_handler,
    backtest_handler,
    task_management_handler,
)


class TestSignalHandlers:
    """Test signal handler instances."""

    def test_account_handler_exists(self) -> None:
        """Test account handler instance exists."""
        assert account_handler is not None
        assert hasattr(account_handler, "connect")
        assert hasattr(account_handler, "bootstrap_tick_pubsub_on_first_live_account")

    def test_backtest_handler_exists(self) -> None:
        """Test backtest handler instance exists."""
        assert backtest_handler is not None
        assert hasattr(backtest_handler, "connect")
        assert hasattr(backtest_handler, "request_backtest_tick_stream")
        assert hasattr(backtest_handler, "enqueue_backtest_tick_publisher")

    def test_task_management_handler_exists(self) -> None:
        """Test task management handler instance exists."""
        assert task_management_handler is not None
        assert hasattr(task_management_handler, "connect")
        assert hasattr(task_management_handler, "request_market_task_cancel")
        assert hasattr(task_management_handler, "handle_market_task_cancel_requested")

    def test_handler_classes_importable(self) -> None:
        """Test that handler classes can be imported."""
        from apps.market.signals import (
            AccountSignalHandler,
            BacktestSignalHandler,
            TaskManagementSignalHandler,
        )

        assert AccountSignalHandler is not None
        assert BacktestSignalHandler is not None
        assert TaskManagementSignalHandler is not None


@pytest.mark.django_db
class TestBacktestSignalHandler:
    """Test BacktestSignalHandler."""

    def test_request_backtest_tick_stream_basic(self) -> None:
        """Test requesting backtest tick stream."""
        from datetime import UTC, datetime

        from apps.market.signals import request_backtest_tick_stream

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

        request_id = request_backtest_tick_stream(
            instrument="EUR_USD",
            start=start,
            end=end,
        )

        assert request_id is not None
        assert isinstance(request_id, str)


@pytest.mark.django_db
class TestTaskManagementSignalHandler:
    """Test TaskManagementSignalHandler."""

    def test_request_market_task_cancel(self) -> None:
        """Test requesting task cancellation."""
        from apps.market.signals import request_market_task_cancel

        # Should not raise exception
        request_market_task_cancel(
            task_name="market.tasks.test_task",
            instance_key="test_instance",
            reason="Test cancellation",
        )

    @pytest.mark.django_db
    def test_handle_market_task_cancel_no_task(self) -> None:
        """Test handling cancellation when task doesn't exist."""
        from apps.market.signals import request_market_task_cancel

        # Should not raise exception even if task doesn't exist
        request_market_task_cancel(
            task_name="market.tasks.nonexistent_task",
            instance_key="test",
        )


@pytest.mark.django_db
class TestAccountSignalHandler:
    """Test AccountSignalHandler."""

    @patch("apps.market.signals.account.transaction")
    def test_bootstrap_on_first_live_account(self, mock_transaction: Any, user: Any) -> None:
        """Test bootstrapping tick pub/sub on first LIVE account."""
        from apps.market.enums import ApiType
        from apps.market.models import OandaAccounts

        # Create first LIVE account
        _ = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
        )

        # Signal should have been triggered
        # transaction.on_commit should have been called
        assert mock_transaction.on_commit.called
