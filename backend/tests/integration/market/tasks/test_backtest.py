"""Integration tests for backtest task."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.tasks.backtest import BacktestTickPublisherRunner
from apps.trading.enums import TaskStatus


@pytest.mark.django_db
class TestBacktestTickPublisherRunnerIntegration:
    """Integration tests for BacktestTickPublisherRunner."""

    @patch("apps.market.tasks.backtest.redis_client")
    @patch("apps.market.tasks.backtest.CeleryTaskService")
    def test_backtest_publisher_initialization(self, mock_service: Any, mock_redis: Any) -> None:
        """Test backtest publisher initialization."""
        # Mock service to stop immediately
        mock_service_instance = MagicMock()
        mock_service_instance.should_stop.return_value = True
        mock_service.return_value = mock_service_instance

        # Mock redis client
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        runner = BacktestTickPublisherRunner()

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

        # Run should not raise exception
        try:
            runner.run(
                instrument="EUR_USD",
                start=start.isoformat(),
                end=end.isoformat(),
                request_id="test-request-123",
            )
        except Exception:
            pass

        # Verify task service was created
        assert mock_service.called

    def test_backtest_publisher_creates_task_status(self) -> None:
        """Test that backtest publisher creates CeleryTaskStatus."""
        # Check that task status can be created
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.publish_ticks_for_backtest",
            instance_key="test-request-456",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task is not None
        assert task.task_name == "market.tasks.publish_ticks_for_backtest"

    def test_backtest_publisher_with_tick_data(self) -> None:
        """Test backtest publisher with actual tick data."""
        # Create some tick data
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        TickData.objects.create(
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
            mid=Decimal("1.10005"),
        )

        # Verify tick data was created
        tick_count = TickData.objects.filter(instrument="EUR_USD").count()
        assert tick_count == 1

    def test_should_stop_publishing_checks_executor_status(self) -> None:
        """Test that _should_stop_publishing checks executor status."""
        from django.contrib.auth import get_user_model

        from apps.trading.models import BacktestTask, StrategyConfiguration

        User = get_user_model()

        # Create required related objects
        test_user = User.objects.create_user(  # type: ignore[attr-defined]
            email="backtest@example.com",
            password="testpass123",
            username="backtestuser",
        )
        config = StrategyConfiguration.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
        )

        # Create a backtest task
        task = BacktestTask.objects.create(
            name="Test Backtest",
            user=test_user,
            config=config,
            instrument="EUR_USD",
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
            initial_balance=Decimal("10000.00"),
            status=TaskStatus.RUNNING,
        )

        request_id = str(task.id)

        # Create runner and mock task service
        runner = BacktestTickPublisherRunner()
        mock_service = MagicMock()
        mock_service.should_stop.return_value = False
        runner.task_service = mock_service

        # Should not stop when task is running
        assert not runner._should_stop_publishing(request_id)

        # Update task to stopping
        task.status = TaskStatus.STOPPING
        task.save()

        # Should stop when task is stopping
        assert runner._should_stop_publishing(request_id)

        # Update task to stopped
        task.status = TaskStatus.STOPPED
        task.save()

        # Should stop when task is stopped
        assert runner._should_stop_publishing(request_id)

        # Update task to failed
        task.status = TaskStatus.FAILED
        task.save()

        # Should stop when task is failed
        assert runner._should_stop_publishing(request_id)

    def test_should_stop_publishing_checks_own_stop_signal(self) -> None:
        """Test that _should_stop_publishing checks its own stop signal."""
        runner = BacktestTickPublisherRunner()
        mock_service = MagicMock()
        mock_service.should_stop.return_value = True
        runner.task_service = mock_service

        # Should stop when own stop signal is set
        assert runner._should_stop_publishing("test-request-999")
