"""Unit tests for TaskController service.

Tests the task lifecycle controller functionality including start, stop,
heartbeat, and control signal checking.
"""

import pytest

from apps.trading.dataclasses import TaskControl
from apps.trading.models import CeleryTaskStatus
from apps.trading.services.controller import TaskController


@pytest.mark.django_db
class TestTaskController:
    """Test suite for TaskController class."""

    def test_start_creates_task_status(self):
        """Test that start() creates a CeleryTaskStatus record."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )

        controller.start(
            celery_task_id="celery-abc-123",
            worker="worker-1",
            meta={"test": "data"},
        )

        # Verify task status was created
        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.status == CeleryTaskStatus.Status.RUNNING
        assert status.celery_task_id == "celery-abc-123"
        assert status.worker == "worker-1"
        assert status.meta == {"test": "data"}
        assert status.started_at is not None
        assert status.last_heartbeat_at is not None
        assert status.stopped_at is None

    def test_start_updates_existing_task_status(self):
        """Test that start() updates an existing CeleryTaskStatus record."""
        # Create initial status
        CeleryTaskStatus.objects.create(
            task_name="test.task",
            instance_key="test-123",
            status=CeleryTaskStatus.Status.STOPPED,
            celery_task_id="old-id",
        )

        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )

        controller.start(
            celery_task_id="new-id",
            worker="worker-2",
        )

        # Verify status was updated
        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.status == CeleryTaskStatus.Status.RUNNING
        assert status.celery_task_id == "new-id"
        assert status.worker == "worker-2"

    def test_heartbeat_updates_timestamp(self):
        """Test that heartbeat() updates the last_heartbeat_at timestamp."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        # Get initial heartbeat time
        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        initial_heartbeat = status.last_heartbeat_at

        # Send heartbeat with force=True to bypass throttling
        controller.heartbeat(force=True)

        # Verify heartbeat was updated
        status.refresh_from_db()
        assert status.last_heartbeat_at > initial_heartbeat

    def test_heartbeat_updates_status_message(self):
        """Test that heartbeat() can update the status message."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        controller.heartbeat(
            status_message="Processing tick 100",
            force=True,
        )

        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.status_message == "Processing tick 100"

    def test_heartbeat_merges_meta_updates(self):
        """Test that heartbeat() merges meta updates with existing meta."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start(meta={"key1": "value1", "key2": "value2"})

        controller.heartbeat(
            meta_update={"key2": "updated", "key3": "value3"},
            force=True,
        )

        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.meta == {
            "key1": "value1",
            "key2": "updated",
            "key3": "value3",
        }

    def test_check_control_returns_no_stop_when_running(self):
        """Test that check_control() returns should_stop=False when running."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        control = controller.check_control(force=True)

        assert isinstance(control, TaskControl)
        assert control.should_stop is False
        assert control.should_pause is False

    def test_check_control_returns_stop_when_requested(self):
        """Test that check_control() returns should_stop=True when stop requested."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        # Request stop
        CeleryTaskStatus.objects.filter(
            task_name="test.task",
            instance_key="test-123",
        ).update(status=CeleryTaskStatus.Status.STOP_REQUESTED)

        control = controller.check_control(force=True)

        assert control.should_stop is True

    def test_stop_marks_task_as_stopped(self):
        """Test that stop() marks the task as stopped."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        controller.stop(status_message="Task completed successfully")

        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.status == CeleryTaskStatus.Status.STOPPED
        assert status.status_message == "Task completed successfully"
        assert status.stopped_at is not None

    def test_stop_with_failed_marks_task_as_failed(self):
        """Test that stop(failed=True) marks the task as failed."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller.start()

        controller.stop(
            status_message="Task failed due to error",
            failed=True,
        )

        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        assert status.status == CeleryTaskStatus.Status.FAILED
        assert status.status_message == "Task failed due to error"
        assert status.stopped_at is not None

    def test_multiple_controllers_same_task_share_state(self):
        """Test that multiple controllers for the same task share state."""
        controller1 = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )
        controller1.start()

        # Create second controller for same task
        controller2 = TaskController(
            task_name="test.task",
            instance_key="test-123",
        )

        # Request stop via database
        CeleryTaskStatus.objects.filter(
            task_name="test.task",
            instance_key="test-123",
        ).update(status=CeleryTaskStatus.Status.STOP_REQUESTED)

        # Both controllers should see the stop request
        control1 = controller1.check_control(force=True)
        control2 = controller2.check_control(force=True)

        assert control1.should_stop is True
        assert control2.should_stop is True

    def test_different_instance_keys_are_independent(self):
        """Test that different instance keys maintain independent state."""
        controller1 = TaskController(
            task_name="test.task",
            instance_key="instance-1",
        )
        controller1.start()

        controller2 = TaskController(
            task_name="test.task",
            instance_key="instance-2",
        )
        controller2.start()

        # Request stop for instance-1 only
        CeleryTaskStatus.objects.filter(
            task_name="test.task",
            instance_key="instance-1",
        ).update(status=CeleryTaskStatus.Status.STOP_REQUESTED)

        # Only controller1 should see the stop request
        control1 = controller1.check_control(force=True)
        control2 = controller2.check_control(force=True)

        assert control1.should_stop is True
        assert control2.should_stop is False

    def test_heartbeat_throttling(self):
        """Test that heartbeat() is throttled by default."""
        import time

        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
            heartbeat_interval_seconds=10.0,  # Long interval
        )
        controller.start()

        # Get initial heartbeat time
        status = CeleryTaskStatus.objects.get(
            task_name="test.task",
            instance_key="test-123",
        )
        initial_heartbeat = status.last_heartbeat_at

        # Small sleep to ensure time has passed
        time.sleep(0.01)

        # Try to send heartbeat without force (should be throttled)
        controller.heartbeat()

        # Verify heartbeat was NOT updated (throttled)
        status.refresh_from_db()
        # Use a tolerance check since database timestamps might have microsecond differences
        time_diff = abs((status.last_heartbeat_at - initial_heartbeat).total_seconds())
        assert time_diff < 0.1, (
            f"Heartbeat was updated when it should have been throttled (diff: {time_diff}s)"
        )

        # Now send with force=True (should bypass throttling)
        time.sleep(0.01)
        controller.heartbeat(force=True)

        # Verify heartbeat WAS updated
        status.refresh_from_db()
        assert status.last_heartbeat_at > initial_heartbeat

    def test_check_control_throttling(self):
        """Test that check_control() is throttled by default."""
        controller = TaskController(
            task_name="test.task",
            instance_key="test-123",
            stop_check_interval_seconds=10.0,  # Long interval
        )
        controller.start()

        # First check should query database
        control1 = controller.check_control()
        assert control1.should_stop is False

        # Request stop
        CeleryTaskStatus.objects.filter(
            task_name="test.task",
            instance_key="test-123",
        ).update(status=CeleryTaskStatus.Status.STOP_REQUESTED)

        # Second check without force should use cached value (throttled)
        control2 = controller.check_control()
        assert control2.should_stop is False  # Still cached old value

        # Check with force=True should query database
        control3 = controller.check_control(force=True)
        assert control3.should_stop is True  # Now sees the stop request
