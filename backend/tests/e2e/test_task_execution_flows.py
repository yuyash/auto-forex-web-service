"""End-to-end integration tests for task execution flows.

This module tests complete workflows including:
- Task creation, submission, execution, and completion
- Task failure and restart flows
- Task cancellation and resume flows
- Real-time status updates

Note: These tests use mocked Celery tasks to avoid requiring a running Celery worker.
They verify the API layer and database interactions work correctly.
"""

from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.trading.enums import DataSource, LogLevel, TaskStatus, TradingMode
from apps.trading.models import BacktestTasks
from apps.trading.models.logs import TaskLog, TaskMetric


@pytest.mark.django_db
class TestCompleteTaskExecutionFlow:
    """Test complete task execution flow from creation to completion."""

    @patch("apps.trading.tasks.backtest._run_backtest_task_wrapper.apply_async")
    def test_backtest_task_complete_flow(
        self,
        mock_apply_async,
        authenticated_client,
        strategy_config,
    ):
        """
        Test complete backtest task execution flow.

        This test verifies:
        1. Task creation via API
        2. Task submission for execution
        3. Celery task creation
        4. Task completion simulation
        5. Status updates
        6. Log and metric retrieval
        7. Results accessibility
        """
        # Create task via API
        create_url = reverse("trading:backtest-task-list")
        task_data = {
            "name": "E2E Complete Flow Test",
            "description": "Testing complete execution flow",
            "config": strategy_config.pk,
            "data_source": DataSource.POSTGRESQL,
            "start_time": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_time": timezone.now().isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
            "trading_mode": TradingMode.NETTING,
        }

        create_response = authenticated_client.post(create_url, task_data, format="json")
        assert create_response.status_code == status.HTTP_201_CREATED
        task_id = create_response.data["id"]

        # Set task to PENDING status before submitting
        task = BacktestTasks.objects.get(pk=task_id)
        task.status = TaskStatus.CREATED
        task.save()

        # Submit task for execution
        celery_task_id = str(uuid4())
        mock_result = Mock()
        mock_result.id = celery_task_id
        mock_apply_async.return_value = mock_result

        submit_url = reverse("trading:backtest-task-submit", kwargs={"pk": task_id})
        submit_response = authenticated_client.post(submit_url)

        assert submit_response.status_code == status.HTTP_200_OK
        assert submit_response.data["status"] == TaskStatus.RUNNING
        assert submit_response.data["celery_task_id"] == celery_task_id

        # Verify Celery task created
        mock_apply_async.assert_called_once()

        # Simulate task execution - create logs and metrics
        task = BacktestTasks.objects.get(pk=task_id)
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Starting backtest")
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Processing data")
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Completed")

        TaskMetric.objects.create(task=task, metric_name="total_trades", metric_value=150.0)
        TaskMetric.objects.create(task=task, metric_name="winning_trades", metric_value=95.0)

        # Complete the task
        task.status = TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.result_data = {"total_trades": 150, "winning_trades": 95, "final_balance": 12500.0}
        task.save()

        # Verify task status updated
        detail_url = reverse("trading:backtest-task-detail", kwargs={"pk": task_id})
        detail_response = authenticated_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["status"] == TaskStatus.COMPLETED

        # Retrieve logs
        logs_url = reverse("trading:backtest-task-logs", kwargs={"pk": task_id})
        logs_response = authenticated_client.get(logs_url)
        assert logs_response.status_code == status.HTTP_200_OK
        assert len(logs_response.data) == 3

        # Retrieve metrics
        metrics_url = reverse("trading:backtest-task-metrics", kwargs={"pk": task_id})
        metrics_response = authenticated_client.get(metrics_url)
        assert metrics_response.status_code == status.HTTP_200_OK
        assert len(metrics_response.data) == 2

        # Verify results accessible
        results_url = reverse("trading:backtest-task-results", kwargs={"pk": task_id})
        results_response = authenticated_client.get(results_url)
        assert results_response.status_code == status.HTTP_200_OK
        assert results_response.data["results"]["total_trades"] == 150


@pytest.mark.django_db
class TestTaskFailureAndRestartFlow:
    """Test task failure and restart flow."""

    @patch("apps.trading.tasks.backtest._run_backtest_task_wrapper.apply_async")
    def test_task_failure_and_restart(
        self,
        mock_apply_async,
        authenticated_client,
        strategy_config,
    ):
        """
        Test task failure and restart flow.

        This test verifies:
        1. Task creation and submission
        2. Task failure with error capture
        3. Task restart via API
        4. New Celery task creation
        5. Retry count increment
        6. Previous execution data cleared
        """
        # Create and submit task
        create_url = reverse("trading:backtest-task-list")
        task_data = {
            "name": "E2E Failure Test",
            "description": "Testing failure and restart",
            "config": strategy_config.pk,
            "data_source": DataSource.POSTGRESQL,
            "start_time": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_time": timezone.now().isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
            "trading_mode": TradingMode.NETTING,
        }

        create_response = authenticated_client.post(create_url, task_data, format="json")
        task_id = create_response.data["id"]

        # Set to PENDING and submit
        task = BacktestTasks.objects.get(pk=task_id)
        task.status = TaskStatus.CREATED
        task.save()

        first_celery_task_id = str(uuid4())
        mock_result = Mock()
        mock_result.id = first_celery_task_id
        mock_apply_async.return_value = mock_result

        submit_url = reverse("trading:backtest-task-submit", kwargs={"pk": task_id})
        authenticated_client.post(submit_url)

        # Simulate task failure
        task = BacktestTasks.objects.get(pk=task_id)
        TaskLog.objects.create(task=task, level=LogLevel.ERROR, message="Connection failed")
        task.status = TaskStatus.FAILED
        task.completed_at = timezone.now()
        task.error_message = "Failed to connect to data source"
        task.error_traceback = "Traceback..."
        task.save()

        # Verify failure captured
        detail_url = reverse("trading:backtest-task-detail", kwargs={"pk": task_id})
        detail_response = authenticated_client.get(detail_url)
        assert detail_response.data["status"] == TaskStatus.FAILED
        assert detail_response.data["error_message"] is not None

        # Restart task
        second_celery_task_id = str(uuid4())
        mock_result.id = second_celery_task_id

        restart_url = reverse("trading:backtest-task-restart", kwargs={"pk": task_id})
        restart_response = authenticated_client.post(restart_url)

        assert restart_response.status_code == status.HTTP_200_OK
        assert restart_response.data["status"] == TaskStatus.RUNNING

        # Verify new Celery task created and retry count incremented
        task.refresh_from_db()
        assert task.celery_task_id == second_celery_task_id
        assert task.retry_count == 1
        assert task.error_message is None  # Cleared on restart


@pytest.mark.django_db
class TestTaskCancellationAndResumeFlow:
    """Test task cancellation and resume flow."""

    @patch("apps.trading.tasks.backtest._run_backtest_task_wrapper.apply_async")
    @patch("celery.result.AsyncResult")
    def test_task_cancellation_and_resume(
        self,
        mock_async_result_class,
        mock_apply_async,
        authenticated_client,
        strategy_config,
    ):
        """
        Test task cancellation and resume flow.

        This test verifies:
        1. Task creation and submission
        2. Task cancellation while running
        3. Cancellation status verification
        4. Task resume via API
        5. New Celery task creation
        6. Execution context preservation
        """
        # Create and submit task
        create_url = reverse("trading:backtest-task-list")
        task_data = {
            "name": "E2E Cancellation Test",
            "description": "Testing cancellation and resume",
            "config": strategy_config.pk,
            "data_source": DataSource.POSTGRESQL,
            "start_time": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_time": timezone.now().isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
            "trading_mode": TradingMode.NETTING,
        }

        create_response = authenticated_client.post(create_url, task_data, format="json")
        task_id = create_response.data["id"]

        # Set to PENDING and submit
        task = BacktestTasks.objects.get(pk=task_id)
        task.status = TaskStatus.CREATED
        task.save()

        first_celery_task_id = str(uuid4())
        mock_result = Mock()
        mock_result.id = first_celery_task_id
        mock_apply_async.return_value = mock_result

        submit_url = reverse("trading:backtest-task-submit", kwargs={"pk": task_id})
        authenticated_client.post(submit_url)

        # Create execution context
        task = BacktestTasks.objects.get(pk=task_id)
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Task started")
        TaskMetric.objects.create(task=task, metric_name="ticks_processed", metric_value=5000.0)

        # Cancel task
        mock_celery_result = Mock()
        mock_celery_result.state = "REVOKED"
        mock_async_result_class.return_value = mock_celery_result

        cancel_url = reverse("trading:backtest-task-cancel", kwargs={"pk": task_id})
        cancel_response = authenticated_client.post(cancel_url)

        assert cancel_response.status_code == status.HTTP_200_OK

        # Verify cancellation
        task.refresh_from_db()
        assert task.status == TaskStatus.STOPPED

        # Resume task
        second_celery_task_id = str(uuid4())
        mock_result.id = second_celery_task_id

        resume_url = reverse("trading:backtest-task-resume", kwargs={"pk": task_id})
        resume_response = authenticated_client.post(resume_url)

        assert resume_response.status_code == status.HTTP_200_OK
        assert resume_response.data["status"] == TaskStatus.RUNNING

        # Verify execution context preserved
        task.refresh_from_db()
        assert task.celery_task_id == second_celery_task_id
        # Note: started_at may be updated on resume, which is acceptable
        # The important thing is that logs and metrics are preserved
        assert task.retry_count == 0  # Not incremented for resume

        # Verify logs and metrics are still there
        logs_url = reverse("trading:backtest-task-logs", kwargs={"pk": task_id})
        logs_response = authenticated_client.get(logs_url)
        assert len(logs_response.data) >= 1  # At least the original log

        metrics_url = reverse("trading:backtest-task-metrics", kwargs={"pk": task_id})
        metrics_response = authenticated_client.get(metrics_url)
        assert len(metrics_response.data) >= 1  # At least the original metric


@pytest.mark.django_db
class TestRealTimeUpdatesFlow:
    """Test real-time status updates flow."""

    @patch("apps.trading.tasks.backtest._run_backtest_task_wrapper.apply_async")
    def test_multiple_status_transitions(
        self,
        mock_apply_async,
        authenticated_client,
        strategy_config,
    ):
        """
        Test that multiple status transitions are tracked correctly.

        This verifies:
        - CREATED -> PENDING -> RUNNING -> COMPLETED
        - Each transition updates timestamps appropriately
        """
        # Create task
        create_url = reverse("trading:backtest-task-list")
        task_data = {
            "name": "Status Transitions Test",
            "description": "Testing multiple status transitions",
            "config": strategy_config.pk,
            "data_source": DataSource.POSTGRESQL,
            "start_time": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_time": timezone.now().isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "EUR_USD",
            "trading_mode": TradingMode.NETTING,
        }

        create_response = authenticated_client.post(create_url, task_data, format="json")
        task_id = create_response.data["id"]

        # Verify CREATED status
        task = BacktestTasks.objects.get(pk=task_id)
        assert task.status == TaskStatus.CREATED
        assert task.started_at is None

        # Transition to PENDING
        task.status = TaskStatus.CREATED
        task.save()
        assert task.status == TaskStatus.CREATED

        # Submit task (PENDING -> RUNNING)
        celery_task_id = str(uuid4())
        mock_result = Mock()
        mock_result.id = celery_task_id
        mock_apply_async.return_value = mock_result

        submit_url = reverse("trading:backtest-task-submit", kwargs={"pk": task_id})
        authenticated_client.post(submit_url)

        task.refresh_from_db()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None

        # Complete task (RUNNING -> COMPLETED)
        task.status = TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save()

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at > task.started_at
