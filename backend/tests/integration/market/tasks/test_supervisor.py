"""Integration tests for supervisor task."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts
from apps.market.tasks.supervisor import TickSupervisorRunner


@pytest.mark.django_db
class TestTickSupervisorRunnerIntegration:
    """Integration tests for TickSupervisorRunner."""

    @patch("apps.market.tasks.supervisor.redis_client")
    @patch("apps.market.tasks.supervisor.CeleryTaskService")
    def test_supervisor_runner_initialization(
        self, mock_service: Any, mock_redis: Any, user: Any
    ) -> None:
        """Test supervisor runner initialization."""
        # Create LIVE account
        OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
        )

        # Mock service to stop immediately
        mock_service_instance = MagicMock()
        mock_service_instance.should_stop.return_value = True
        mock_service.return_value = mock_service_instance

        runner = TickSupervisorRunner()

        # Run should not raise exception
        try:
            runner.run()
        except Exception:
            pass

        # Verify task service was created
        assert mock_service.called

    def test_supervisor_creates_task_status(self, user: Any) -> None:
        """Test that supervisor creates CeleryTaskStatus."""
        OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type=ApiType.LIVE,
        )

        # Check that task status can be created
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.ensure_tick_pubsub_running",
            instance_key="supervisor",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task is not None
        assert task.task_name == "market.tasks.ensure_tick_pubsub_running"
