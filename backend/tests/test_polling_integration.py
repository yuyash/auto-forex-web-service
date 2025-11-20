"""
Integration tests for HTTP polling flow.

Tests the complete polling flow:
- Start task → poll status → task completes → polling stops
- Log retrieval during task execution
- Progress updates

Requirements: 1.2, 1.4, 4.5, 4.7
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

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


@pytest.mark.django_db
class TestPollingIntegration:
    """Integration tests for complete polling flow."""

    def test_complete_polling_flow(self, api_client, user, strategy_config):
        """
        Test complete flow: start task → poll status → task completes → polling stops.

        This test simulates the frontend polling behavior:
        1. Create and start a task
        2. Poll status endpoint multiple times while task is running
        3. Task completes
        4. Final poll shows completed status
        5. Verify polling should stop (status is no longer RUNNING)

        Requirements: 1.2, 4.5, 4.7
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Step 1: Create a backtest task
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Integration Test Backtest",
            description="Test polling flow",
            status=TaskStatus.CREATED,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Step 2: Start the task (simulate task execution starting)
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=0,
            started_at=timezone.now(),
            logs=[
                {
                    "timestamp": timezone.now().isoformat(),
                    "level": "INFO",
                    "message": "Task started",
                }
            ],
        )
        task.status = TaskStatus.RUNNING
        task.save()

        # Step 3: Poll status endpoint (first poll - task just started)
        status_url = reverse("trading:backtest_task_status", kwargs={"task_id": task.id})
        response = api_client.get(status_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        assert response.data["execution"]["progress"] == 0
        assert response.data["execution"]["status"] == TaskStatus.RUNNING

        # Step 4: Simulate progress update (task is running)
        execution.progress = 25
        execution.logs.append(
            {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": "Processing 25% complete",
            }
        )
        execution.save()

        # Step 5: Poll status again (second poll - task progressing)
        response = api_client.get(status_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        assert response.data["execution"]["progress"] == 25

        # Step 6: Simulate more progress
        execution.progress = 75
        execution.logs.append(
            {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": "Processing 75% complete",
            }
        )
        execution.save()

        # Step 7: Poll status again (third poll - task almost done)
        response = api_client.get(status_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        assert response.data["execution"]["progress"] == 75

        # Step 8: Task completes
        execution.status = TaskStatus.COMPLETED
        execution.progress = 100
        execution.completed_at = timezone.now()
        execution.logs.append(
            {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": "Task completed successfully",
            }
        )
        execution.save()

        task.status = TaskStatus.COMPLETED
        task.save()

        # Step 9: Final poll (task completed)
        response = api_client.get(status_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.COMPLETED
        assert response.data["execution"]["progress"] == 100
        assert response.data["execution"]["status"] == TaskStatus.COMPLETED
        assert response.data["execution"]["completed_at"] is not None

        # Step 10: Verify polling should stop
        # Frontend should detect status is not RUNNING and stop polling
        assert response.data["status"] != TaskStatus.RUNNING

    def test_log_retrieval_during_execution(self, api_client, user, strategy_config):
        """
        Test log retrieval during task execution.

        Simulates polling logs endpoint while task is running and generating logs.

        Requirements: 1.4, 4.5
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a running task with logs
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Log Test Backtest",
            description="Test log retrieval",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=30,
            started_at=timezone.now(),
            logs=[
                {
                    "timestamp": timezone.now().isoformat(),
                    "level": "INFO",
                    "message": "Task started",
                },
                {
                    "timestamp": (timezone.now() + timedelta(seconds=1)).isoformat(),
                    "level": "INFO",
                    "message": "Loading historical data",
                },
                {
                    "timestamp": (timezone.now() + timedelta(seconds=2)).isoformat(),
                    "level": "INFO",
                    "message": "Processing day 1 of 7",
                },
            ],
        )

        # Poll logs endpoint
        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.id})
        response = api_client.get(logs_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3
        # Logs are returned in reverse chronological order (newest first)
        assert response.data["results"][2]["message"] == "Task started"
        assert response.data["results"][2]["level"] == "INFO"
        assert response.data["results"][2]["execution_number"] == 1

        # Simulate more logs being added
        execution.logs.extend(
            [
                {
                    "timestamp": (timezone.now() + timedelta(seconds=3)).isoformat(),
                    "level": "INFO",
                    "message": "Processing day 2 of 7",
                },
                {
                    "timestamp": (timezone.now() + timedelta(seconds=4)).isoformat(),
                    "level": "WARNING",
                    "message": "Low liquidity detected",
                },
            ]
        )
        execution.save()

        # Poll logs again
        response = api_client.get(logs_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 5
        assert len(response.data["results"]) == 5
        # Logs are in reverse chronological order, so newest logs are first
        assert response.data["results"][0]["level"] == "WARNING"
        assert response.data["results"][1]["message"] == "Processing day 2 of 7"

    def test_progress_updates_during_execution(self, api_client, user, strategy_config):
        """
        Test progress updates during task execution.

        Verifies that progress values are correctly updated and retrieved.

        Requirements: 1.2, 4.5
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a running task
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Progress Test Backtest",
            description="Test progress updates",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=0,
            started_at=timezone.now(),
        )

        status_url = reverse("trading:backtest_task_status", kwargs={"task_id": task.id})

        # Test progress at 0%
        response = api_client.get(status_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["execution"]["progress"] == 0

        # Update to 20%
        execution.progress = 20
        execution.save()
        response = api_client.get(status_url)
        assert response.data["execution"]["progress"] == 20

        # Update to 50%
        execution.progress = 50
        execution.save()
        response = api_client.get(status_url)
        assert response.data["execution"]["progress"] == 50

        # Update to 80%
        execution.progress = 80
        execution.save()
        response = api_client.get(status_url)
        assert response.data["execution"]["progress"] == 80

        # Update to 100% (completed)
        execution.progress = 100
        execution.status = TaskStatus.COMPLETED
        execution.completed_at = timezone.now()
        execution.save()

        task.status = TaskStatus.COMPLETED
        task.save()

        response = api_client.get(status_url)
        assert response.data["execution"]["progress"] == 100
        assert response.data["execution"]["status"] == TaskStatus.COMPLETED

    def test_polling_with_task_failure(self, api_client, user, strategy_config):
        """
        Test polling flow when task fails.

        Verifies that failure status is correctly reported and polling should stop.

        Requirements: 1.2, 4.5, 4.7
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a running task
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Failure Test Backtest",
            description="Test task failure",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=45,
            started_at=timezone.now(),
            logs=[
                {
                    "timestamp": timezone.now().isoformat(),
                    "level": "INFO",
                    "message": "Task started",
                }
            ],
        )

        status_url = reverse("trading:backtest_task_status", kwargs={"task_id": task.id})

        # Poll while running
        response = api_client.get(status_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING

        # Simulate task failure
        execution.status = TaskStatus.FAILED
        execution.completed_at = timezone.now()
        execution.error_message = "Insufficient historical data"
        execution.logs.append(
            {
                "timestamp": timezone.now().isoformat(),
                "level": "ERROR",
                "message": "Task failed: Insufficient historical data",
            }
        )
        execution.save()

        task.status = TaskStatus.FAILED
        task.save()

        # Poll after failure
        response = api_client.get(status_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.FAILED
        assert response.data["execution"]["status"] == TaskStatus.FAILED
        assert response.data["execution"]["error_message"] == "Insufficient historical data"

        # Verify polling should stop (status is not RUNNING)
        assert response.data["status"] != TaskStatus.RUNNING

        # Verify error log is retrievable
        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.id})
        response = api_client.get(logs_url)
        assert response.status_code == status.HTTP_200_OK
        assert any(log["level"] == "ERROR" for log in response.data["results"])

    def test_polling_with_pagination(self, api_client, user, strategy_config):
        """
        Test log retrieval with pagination during execution.

        Requirements: 1.4
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a task with many logs
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Pagination Test Backtest",
            description="Test log pagination",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Generate 150 log entries
        logs = []
        for i in range(150):
            logs.append(
                {
                    "timestamp": (timezone.now() + timedelta(seconds=i)).isoformat(),
                    "level": "INFO",
                    "message": f"Processing step {i + 1}",
                }
            )

        TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.id,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=50,
            started_at=timezone.now(),
            logs=logs,
        )

        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.id})

        # Get first page (default limit is 100)
        response = api_client.get(logs_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 150
        assert len(response.data["results"]) == 100
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        # Get second page
        response = api_client.get(logs_url, {"offset": 100})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 150
        assert len(response.data["results"]) == 50
        assert response.data["next"] is None
        assert response.data["previous"] is not None

        # Get with custom limit
        response = api_client.get(logs_url, {"limit": 25})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 25
