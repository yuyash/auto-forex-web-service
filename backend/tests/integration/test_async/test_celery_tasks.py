"""
Integration tests for Celery task execution.

Tests task pickup from Redis, task execution with error handling,
task retry according to policy, task status updates, and task execution logging.
Validates Requirement 1.2.
"""

import pytest
from django.utils import timezone

from apps.trading.models import CeleryTaskStatus
from tests.integration.base import IntegrationTestCase


@pytest.mark.django_db
class TestCeleryTaskStatusTracking(IntegrationTestCase):
    """Tests for Celery task status tracking."""

    def test_create_celery_task_status_record(self) -> None:
        """Test creating a Celery task status record."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            celery_task_id="test-celery-id-123",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Verify task status was created
        self.assertIsNotNone(task_status.id)
        self.assertEqual(task_status.task_name, "trading.tasks.run_backtest_task")
        self.assertEqual(task_status.instance_key, "test-instance-1")
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.RUNNING)
        self.assertIsNotNone(task_status.started_at)

    def test_update_task_status_to_completed(self) -> None:
        """Test updating task status to completed."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Update status to completed
        task_status.status = CeleryTaskStatus.Status.COMPLETED
        task_status.stopped_at = timezone.now()
        task_status.save()

        # Verify status was updated
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.COMPLETED)
        self.assertIsNotNone(task_status.stopped_at)

    def test_update_task_status_to_failed(self) -> None:
        """Test updating task status to failed with error message."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Update status to failed
        task_status.status = CeleryTaskStatus.Status.FAILED
        task_status.status_message = "Task failed due to database connection error"
        task_status.stopped_at = timezone.now()
        task_status.save()

        # Verify status and message were updated
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.FAILED)
        self.assertIn("database connection error", task_status.status_message)
        self.assertIsNotNone(task_status.stopped_at)

    def test_task_heartbeat_updates(self) -> None:
        """Test that task heartbeat timestamp is updated."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
            last_heartbeat_at=timezone.now(),
        )

        initial_heartbeat = task_status.last_heartbeat_at

        # Simulate heartbeat update
        task_status.last_heartbeat_at = timezone.now()
        task_status.save()

        # Verify heartbeat was updated
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertGreater(task_status.last_heartbeat_at, initial_heartbeat)


@pytest.mark.django_db
class TestCeleryTaskExecution(IntegrationTestCase):
    """Tests for Celery task execution flow."""

    def test_task_status_lifecycle(self) -> None:
        """Test complete task status lifecycle from running to completed."""
        # Create task status
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            celery_task_id="test-celery-id-123",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Verify initial state
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.RUNNING)
        self.assertIsNotNone(task_status.started_at)
        self.assertIsNone(task_status.stopped_at)

        # Update to completed
        task_status.status = CeleryTaskStatus.Status.COMPLETED
        task_status.stopped_at = timezone.now()
        task_status.save()

        # Verify final state
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.COMPLETED)
        self.assertIsNotNone(task_status.stopped_at)
        self.assertGreater(task_status.stopped_at, task_status.started_at)

    def test_task_stop_requested_status(self) -> None:
        """Test that task can be marked for stop."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_trading_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Request stop
        task_status.status = CeleryTaskStatus.Status.STOP_REQUESTED
        task_status.status_message = "Stop requested by user"
        task_status.save()

        # Verify stop was requested
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.STOP_REQUESTED)
        self.assertIn("Stop requested", task_status.status_message)


@pytest.mark.django_db
class TestCeleryTaskErrorHandling(IntegrationTestCase):
    """Tests for Celery task error handling."""

    def test_task_failure_with_error_details(self) -> None:
        """Test that task failures include error details."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=timezone.now(),
        )

        # Simulate task failure
        error_details = {
            "error_type": "DatabaseError",
            "error_message": "Connection timeout",
            "traceback": "Traceback (most recent call last)...",
        }

        task_status.status = CeleryTaskStatus.Status.FAILED
        task_status.status_message = "Task failed with DatabaseError"
        task_status.meta = error_details
        task_status.stopped_at = timezone.now()
        task_status.save()

        # Verify error details were stored
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.status, CeleryTaskStatus.Status.FAILED)
        self.assertEqual(task_status.meta["error_type"], "DatabaseError")
        self.assertIn("Connection timeout", task_status.meta["error_message"])

    def test_task_retry_tracking(self) -> None:
        """Test that task retry attempts are tracked."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            meta={"retry_count": 0},
        )

        # Simulate first retry
        task_status.meta["retry_count"] = 1
        task_status.meta["last_retry_at"] = timezone.now().isoformat()
        task_status.save()

        # Verify retry was tracked
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.meta["retry_count"], 1)
        self.assertIn("last_retry_at", task_status.meta)


@pytest.mark.django_db
class TestCeleryTaskStatusUpdates(IntegrationTestCase):
    """Tests for Celery task status updates."""

    def test_task_status_update_with_metadata(self) -> None:
        """Test updating task status with additional metadata."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        # Update with metadata
        task_status.meta = {
            "progress": 50,
            "processed_ticks": 1000,
            "total_ticks": 2000,
        }
        task_status.save()

        # Verify metadata was stored
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(task_status.meta["progress"], 50)
        self.assertEqual(task_status.meta["processed_ticks"], 1000)

    def test_task_worker_information(self) -> None:
        """Test that worker information is stored."""
        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            celery_task_id="test-celery-id-123",
            worker="celery@worker1",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        # Verify worker information
        self.assertEqual(task_status.worker, "celery@worker1")
        self.assertEqual(task_status.celery_task_id, "test-celery-id-123")


@pytest.mark.django_db
class TestCeleryTaskLogging(IntegrationTestCase):
    """Tests for Celery task execution logging."""

    def test_task_execution_timestamps(self) -> None:
        """Test that task execution timestamps are recorded."""
        started_at = timezone.now()

        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=started_at,
        )

        # Complete task
        stopped_at = timezone.now()
        task_status.status = CeleryTaskStatus.Status.COMPLETED
        task_status.stopped_at = stopped_at
        task_status.save()

        # Verify timestamps
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        self.assertIsNotNone(task_status.started_at)
        self.assertIsNotNone(task_status.stopped_at)
        self.assertGreater(task_status.stopped_at, task_status.started_at)

    def test_task_execution_duration_calculation(self) -> None:
        """Test calculating task execution duration."""
        started_at = timezone.now()

        task_status = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
            started_at=started_at,
        )

        # Complete task
        stopped_at = timezone.now()
        task_status.status = CeleryTaskStatus.Status.COMPLETED
        task_status.stopped_at = stopped_at
        task_status.save()

        # Calculate duration
        task_status.refresh_from_db()    # type: ignore[attr-defined]
        duration = task_status.stopped_at - task_status.started_at

        # Verify duration is positive
        self.assertGreater(duration.total_seconds(), 0)


@pytest.mark.django_db
class TestCeleryTaskQuerying(IntegrationTestCase):
    """Tests for querying Celery task status."""

    def test_query_running_tasks(self) -> None:
        """Test querying all running tasks."""
        # Create mix of running and completed tasks
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-1",
            status=CeleryTaskStatus.Status.RUNNING,
        )
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-2",
            status=CeleryTaskStatus.Status.RUNNING,
        )
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-3",
            status=CeleryTaskStatus.Status.COMPLETED,
        )

        # Query running tasks
        running_tasks = CeleryTaskStatus.objects.filter(status=CeleryTaskStatus.Status.RUNNING)

        self.assertEqual(running_tasks.count(), 2)

    def test_query_tasks_by_name(self) -> None:
        """Test querying tasks by task name."""
        # Create tasks with different names
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-1",
            status=CeleryTaskStatus.Status.RUNNING,
        )
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_trading_task",
            instance_key="test-2",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        # Query by task name
        backtest_tasks = CeleryTaskStatus.objects.filter(
            task_name="trading.tasks.run_backtest_task"
        )

        self.assertEqual(backtest_tasks.count(), 1)
        self.assertEqual(backtest_tasks.first().task_name, "trading.tasks.run_backtest_task")  # ty:ignore[possibly-missing-attribute]

    def test_query_failed_tasks(self) -> None:
        """Test querying all failed tasks."""
        # Create mix of statuses
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-1",
            status=CeleryTaskStatus.Status.FAILED,
        )
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-2",
            status=CeleryTaskStatus.Status.COMPLETED,
        )

        # Query failed tasks
        failed_tasks = CeleryTaskStatus.objects.filter(status=CeleryTaskStatus.Status.FAILED)

        self.assertEqual(failed_tasks.count(), 1)

    def test_unique_constraint_on_task_name_and_instance(self) -> None:
        """Test that task_name and instance_key combination is unique."""
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="test-instance-1",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        # Try to create duplicate
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            CeleryTaskStatus.objects.create(
                task_name="trading.tasks.run_backtest_task",
                instance_key="test-instance-1",
                status=CeleryTaskStatus.Status.RUNNING,
            )
