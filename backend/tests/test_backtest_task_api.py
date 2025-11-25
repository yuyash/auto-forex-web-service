"""
Unit tests for backtest task API endpoints.

Tests the BacktestTask API views including:
- Stop endpoint with running/non-running tasks
- Delete endpoint with running task (should fail)
- Delete endpoint with stopped task (should succeed)
- Status verification endpoint

Requirements: 2.1, 2.3, 2.4, 2.5, 3.1, 3.6
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus, TaskType
from trading.execution_models import TaskExecution
from trading.models import StrategyConfig

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfig.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="MA_CROSSOVER",
        parameters={
            "fast_period": 10,
            "slow_period": 20,
            "instrument": "EUR_USD",
            "granularity": "M5",
        },
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create test backtest task."""
    from datetime import timedelta

    from django.utils import timezone

    return BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        description="Test backtest task",
        status=TaskStatus.CREATED,
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now() - timedelta(days=1),
    )


@pytest.fixture
def running_backtest_task(db, user, strategy_config):
    """Create running backtest task."""
    from datetime import timedelta

    from django.utils import timezone

    task = BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Running Backtest",
        description="Running backtest task",
        status=TaskStatus.RUNNING,
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now() - timedelta(days=1),
    )
    # Create execution
    TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.RUNNING,
        progress=50,
        started_at=timezone.now(),
    )
    return task


@pytest.fixture
def stopped_backtest_task(db, user, strategy_config):
    """Create stopped backtest task."""
    from datetime import timedelta

    from django.utils import timezone

    task = BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Stopped Backtest",
        description="Stopped backtest task",
        status=TaskStatus.STOPPED,
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now() - timedelta(days=1),
    )
    # Create execution
    TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.STOPPED,
        progress=30,
    )
    return task


@pytest.mark.django_db
class TestBacktestTaskStopEndpoint:
    """Test stop endpoint with running/non-running tasks."""

    def test_stop_running_task_success(self, api_client, user, running_backtest_task):
        """
        Test stopping a running task successfully.

        Requirements: 2.1, 2.3, 3.1, 3.2
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Mock TaskLockManager and notification
        with (
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.notifications.send_task_status_notification") as mock_notify,
        ):
            mock_lock_manager = MagicMock()
            mock_lock_manager_class.return_value = mock_lock_manager

            # Make request
            url = reverse(
                "trading:backtest_task_stop", kwargs={"task_id": running_backtest_task.pk}
            )
            response = api_client.post(url)

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            assert response.data["id"] == running_backtest_task.pk
            assert response.data["status"] == TaskStatus.STOPPED
            assert response.data["message"] == "Task stop initiated"

            # Verify cancellation flag was set
            mock_lock_manager.set_cancellation_flag.assert_called_once_with(
                "backtest", running_backtest_task.pk
            )

            # Verify notification was sent
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["user_id"] == user.pk
            assert call_kwargs["task_id"] == running_backtest_task.pk
            assert call_kwargs["status"] == TaskStatus.STOPPED

            # Verify task status was updated
            running_backtest_task.refresh_from_db()
            assert running_backtest_task.status == TaskStatus.STOPPED

    def test_stop_non_running_task_fails(self, api_client, user, backtest_task):
        """
        Test stopping a non-running task returns error.

        Requirements: 2.1, 2.3
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request
        url = reverse("trading:backtest_task_stop", kwargs={"task_id": backtest_task.pk})
        response = api_client.post(url)

        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not running" in response.data["error"].lower()

    def test_stop_nonexistent_task_fails(self, api_client, user):
        """Test stopping a nonexistent task returns 404."""
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request with invalid task ID
        url = reverse("trading:backtest_task_stop", kwargs={"task_id": 99999})
        response = api_client.post(url)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"].lower()

    def test_stop_task_unauthenticated(self, api_client, running_backtest_task):
        """Test stopping a task without authentication fails."""
        # Make request without authentication
        url = reverse("trading:backtest_task_stop", kwargs={"task_id": running_backtest_task.pk})
        response = api_client.post(url)

        # Verify response
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBacktestTaskDeleteEndpoint:
    """Test delete endpoint with running and stopped tasks."""

    def test_delete_running_task_fails(self, api_client, user, running_backtest_task):
        """
        Test deleting a running task returns 409 conflict.

        Requirements: 2.4, 2.5, 7.2
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request
        url = reverse("trading:backtest_task_detail", kwargs={"task_id": running_backtest_task.pk})
        response = api_client.delete(url)

        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot delete" in response.data[0].lower()
        assert "running" in response.data[0].lower()

        # Verify task was not deleted
        assert BacktestTask.objects.filter(id=running_backtest_task.pk).exists()

    def test_delete_stopped_task_succeeds(self, api_client, user, stopped_backtest_task):
        """
        Test deleting a stopped task succeeds.

        Requirements: 2.4, 2.5, 7.2
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request
        url = reverse("trading:backtest_task_detail", kwargs={"task_id": stopped_backtest_task.pk})
        response = api_client.delete(url)

        # Verify response
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify task was deleted
        assert not BacktestTask.objects.filter(id=stopped_backtest_task.pk).exists()

        # Note: TaskExecution records are kept for historical purposes
        # They don't cascade delete with the task

    def test_delete_created_task_succeeds(self, api_client, user, backtest_task):
        """Test deleting a created task succeeds."""
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request
        url = reverse("trading:backtest_task_detail", kwargs={"task_id": backtest_task.pk})
        response = api_client.delete(url)

        # Verify response
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify task was deleted
        assert not BacktestTask.objects.filter(id=backtest_task.pk).exists()

    def test_delete_nonexistent_task_fails(self, api_client, user):
        """Test deleting a nonexistent task returns 404."""
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request with invalid task ID
        url = reverse("trading:backtest_task_detail", kwargs={"task_id": 99999})
        response = api_client.delete(url)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestBacktestTaskStatusEndpoint:
    """Test status verification endpoint."""

    def test_get_status_with_execution(self, api_client, user, running_backtest_task):
        """
        Test getting status for task with execution.

        Requirements: 3.1, 3.6
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Get execution
        execution = running_backtest_task.get_latest_execution()

        # Make request
        url = reverse("trading:backtest_task_status", kwargs={"task_id": running_backtest_task.pk})
        response = api_client.get(url)

        # Verify response matches TaskStatusResponse interface
        assert response.status_code == status.HTTP_200_OK
        assert response.data["task_id"] == running_backtest_task.pk
        assert response.data["task_type"] == "backtest"
        assert response.data["status"] == TaskStatus.RUNNING
        assert response.data["progress"] == execution.progress
        assert response.data["started_at"] is not None
        assert response.data["completed_at"] is None
        assert response.data["error_message"] is None

    def test_get_status_without_execution(self, api_client, user, backtest_task):
        """
        Test getting status for task without execution.

        Requirements: 3.1, 3.6
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request
        url = reverse("trading:backtest_task_status", kwargs={"task_id": backtest_task.pk})
        response = api_client.get(url)

        # Verify response matches TaskStatusResponse interface
        assert response.status_code == status.HTTP_200_OK
        assert response.data["task_id"] == backtest_task.pk
        assert response.data["task_type"] == "backtest"
        assert response.data["status"] == TaskStatus.CREATED
        assert response.data["progress"] == 0
        assert response.data["started_at"] is None
        assert response.data["completed_at"] is None
        assert response.data["error_message"] is None

    def test_get_status_nonexistent_task_fails(self, api_client, user):
        """Test getting status for nonexistent task returns 404."""
        # Authenticate
        api_client.force_authenticate(user=user)

        # Make request with invalid task ID
        url = reverse("trading:backtest_task_status", kwargs={"task_id": 99999})
        response = api_client.get(url)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"].lower()

    def test_get_status_unauthenticated(self, api_client, backtest_task):
        """Test getting status without authentication fails."""
        # Make request without authentication
        url = reverse("trading:backtest_task_status", kwargs={"task_id": backtest_task.pk})
        response = api_client.get(url)

        # Verify response
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_status_other_user_task_fails(self, api_client, db, backtest_task):
        """Test getting status for another user's task fails."""
        # Create another user
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123",
        )

        # Authenticate as other user
        api_client.force_authenticate(user=other_user)

        # Make request for first user's task
        url = reverse("trading:backtest_task_status", kwargs={"task_id": backtest_task.pk})
        response = api_client.get(url)

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
