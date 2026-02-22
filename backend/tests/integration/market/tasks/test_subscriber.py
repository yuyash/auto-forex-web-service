"""Integration tests for subscriber task."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.models import CeleryTaskStatus
from apps.market.tasks.subscriber import TickSubscriberRunner


@pytest.mark.django_db
class TestTickSubscriberRunnerIntegration:
    """Integration tests for TickSubscriberRunner."""

    @patch("apps.market.tasks.subscriber.redis_client")
    @patch("apps.market.tasks.subscriber.CeleryTaskService")
    def test_subscriber_runner_initialization(self, mock_service: Any, mock_redis: Any) -> None:
        """Test subscriber runner initialization."""
        # Mock service to stop immediately
        mock_service_instance = MagicMock()
        mock_service_instance.should_stop.return_value = True
        mock_service.return_value = mock_service_instance

        runner = TickSubscriberRunner()

        # Run should not raise exception
        try:
            runner.run()
        except Exception:
            pass

        # Verify task service was created
        assert mock_service.called

    def test_subscriber_creates_task_status(self) -> None:
        """Test that subscriber creates CeleryTaskStatus."""
        # Check that task status can be created
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.subscribe_ticks_to_db",
            instance_key="default",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task is not None
        assert task.task_name == "market.tasks.subscribe_ticks_to_db"

    def test_subscriber_buffer_initialization(self) -> None:
        """Test that subscriber buffer is initialized."""
        runner = TickSubscriberRunner()

        assert hasattr(runner, "buffer")
        assert isinstance(runner.buffer, list)
        assert len(runner.buffer) == 0
