"""Unit tests for status synchronization utilities."""

from unittest.mock import Mock, patch

import pytest
from celery.result import AsyncResult

from apps.trading.enums import TaskStatus
from apps.trading.models import CeleryTaskStatus
from apps.trading.services.status_sync import sync_task_status_from_celery


@pytest.mark.django_db
class TestSyncTaskStatusFromCelery:
    """Test sync_task_status_from_celery function."""

    def test_skip_sync_for_terminal_states(self) -> None:
        """Test that sync is skipped for terminal states."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.STOPPED
        task.save = Mock()

        sync_task_status_from_celery(task, None)

        task.save.assert_not_called()

    def test_skip_sync_for_paused_state(self) -> None:
        """Test that sync is skipped for PAUSED state."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.PAUSED
        task.save = Mock()

        sync_task_status_from_celery(task, None)

        task.save.assert_not_called()

    @patch("apps.trading.models.CeleryTaskStatus.objects")
    def test_skip_sync_when_stop_requested(self, mock_objects: Mock) -> None:
        """Test that sync is skipped when stop is requested."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.RUNNING
        task.save = Mock()

        celery_status = Mock()
        celery_status.status = CeleryTaskStatus.Status.STOP_REQUESTED
        mock_objects.filter.return_value.first.return_value = celery_status

        sync_task_status_from_celery(task, None)

        task.save.assert_not_called()

    @patch("apps.trading.models.CeleryTaskStatus.objects")
    def test_sync_to_stopped_from_celery_status(self, mock_objects: Mock) -> None:
        """Test syncing to STOPPED from CeleryTaskStatus."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.RUNNING
        task.save = Mock()

        celery_status = Mock()
        celery_status.status = CeleryTaskStatus.Status.STOPPED
        mock_objects.filter.return_value.first.return_value = celery_status

        sync_task_status_from_celery(task, None)

        assert task.status == TaskStatus.STOPPED
        task.save.assert_called_once_with(update_fields=["status", "updated_at"])

    @patch("apps.trading.models.CeleryTaskStatus.objects")
    def test_sync_from_celery_result_when_no_celery_status(self, mock_objects: Mock) -> None:
        """Test syncing from Celery AsyncResult when CeleryTaskStatus not found."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.CREATED
        task.save = Mock()

        mock_objects.filter.return_value.first.return_value = None

        celery_result = Mock(spec=AsyncResult)
        celery_result.state = "STARTED"

        sync_task_status_from_celery(task, celery_result)

        assert task.status == TaskStatus.RUNNING
        task.save.assert_called_once_with(update_fields=["status", "updated_at"])

    @patch("apps.trading.models.CeleryTaskStatus.objects")
    def test_celery_status_priority_over_async_result(self, mock_objects: Mock) -> None:
        """Test that CeleryTaskStatus has priority over AsyncResult."""
        task = Mock()
        task.pk = 1
        task.status = TaskStatus.RUNNING
        task.save = Mock()

        celery_status = Mock()
        celery_status.status = CeleryTaskStatus.Status.STOPPED
        mock_objects.filter.return_value.first.return_value = celery_status

        celery_result = Mock(spec=AsyncResult)
        celery_result.state = "STARTED"

        sync_task_status_from_celery(task, celery_result)

        assert task.status == TaskStatus.STOPPED
        task.save.assert_called_once_with(update_fields=["status", "updated_at"])
