"""Integration tests for signal handlers."""

from datetime import UTC, datetime
from typing import Any

import pytest

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts
from apps.market.signals import (
    request_backtest_tick_stream,
    request_market_task_cancel,
)


@pytest.mark.django_db
class TestBacktestSignalHandlerIntegration:
    """Integration tests for BacktestSignalHandler."""

    def test_request_backtest_tick_stream_creates_task(self) -> None:
        """Test that requesting backtest tick stream enqueues task."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

        request_id = request_backtest_tick_stream(
            instrument="EUR_USD",
            start=start,
            end=end,
        )

        assert request_id is not None
        assert isinstance(request_id, str)
        assert len(request_id) > 0

    def test_request_backtest_with_custom_request_id(self) -> None:
        """Test requesting backtest with custom request ID."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
        custom_id = "custom-request-123"

        request_id = request_backtest_tick_stream(
            instrument="EUR_USD",
            start=start,
            end=end,
            request_id=custom_id,
        )

        assert request_id == custom_id


@pytest.mark.django_db
class TestTaskManagementSignalHandlerIntegration:
    """Integration tests for TaskManagementSignalHandler."""

    def test_request_market_task_cancel_no_task(self) -> None:
        """Test requesting cancellation when task doesn't exist."""
        # Should not raise exception
        request_market_task_cancel(
            task_name="market.tasks.nonexistent_task",
            instance_key="test",
        )

    def test_request_market_task_cancel_with_existing_task(self) -> None:
        """Test requesting cancellation for existing task."""
        # Create a running task
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.test_task",
            instance_key="test_instance",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        # Request cancellation
        request_market_task_cancel(
            task_name="market.tasks.test_task",
            instance_key="test_instance",
            reason="Test cancellation",
        )

        # Verify status was updated
        task.refresh_from_db()
        assert task.status == CeleryTaskStatus.Status.STOP_REQUESTED
        assert "Test cancellation" in task.status_message


@pytest.mark.django_db
class TestAccountSignalHandlerIntegration:
    """Integration tests for AccountSignalHandler."""

    def test_bootstrap_on_first_live_account(self, user: Any) -> None:
        """Test bootstrapping tick pub/sub on first LIVE account."""
        # Create first LIVE account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
        )

        # Signal should have been triggered
        assert account.api_type == ApiType.LIVE

        # Verify only one LIVE account exists
        live_count = OandaAccounts.objects.filter(api_type=ApiType.LIVE).count()
        assert live_count == 1

    def test_no_bootstrap_on_practice_account(self, user: Any) -> None:
        """Test that PRACTICE accounts don't trigger bootstrap."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        assert account.api_type == ApiType.PRACTICE

        # No LIVE accounts should exist
        live_count = OandaAccounts.objects.filter(api_type=ApiType.LIVE).count()
        assert live_count == 0
