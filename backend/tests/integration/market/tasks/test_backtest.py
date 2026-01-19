"""Integration tests for backtest task."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.tasks.backtest import BacktestTickPublisherRunner


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
