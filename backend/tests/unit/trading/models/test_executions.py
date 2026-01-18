"""Unit tests for Executions model."""

import pytest
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions


@pytest.mark.django_db
class TestExecutionsModel:
    """Test suite for Executions model."""

    def test_create_execution_with_valid_data(self):
        """Test creating Executions with valid fields."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        assert execution.id is not None
        assert execution.task_type == TaskType.BACKTEST
        assert execution.task_id == 1
        assert execution.execution_number == 1
        assert execution.status == TaskStatus.RUNNING
        assert execution.progress == 0
        assert execution.created_at is not None

    def test_unique_constraint_on_task_type_task_id_execution_number(self):
        """Test that (task_type, task_id, execution_number) must be unique."""
        # Create first execution
        Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Attempt to create duplicate
        with pytest.raises(Exception):  # IntegrityError or similar
            Executions.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=1,
                execution_number=1,  # Same combination
                status=TaskStatus.RUNNING,
            )

    def test_mark_completed(self):
        """Test marking execution as completed."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        execution.mark_completed()

        assert execution.status == TaskStatus.COMPLETED
        assert execution.completed_at is not None
        assert execution.progress == 100

    def test_mark_failed(self):
        """Test marking execution as failed."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        error = ValueError("Test error")
        execution.mark_failed(error)

        assert execution.status == TaskStatus.FAILED
        assert execution.completed_at is not None
        assert "Test error" in execution.error_message
        assert execution.error_traceback != ""

    def test_update_progress(self):
        """Test updating execution progress."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        execution.update_progress(50)
        assert execution.progress == 50

        execution.update_progress(75)
        assert execution.progress == 75

    def test_add_log(self):
        """Test adding log entries."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        execution.add_log("INFO", "Test log message")

        assert len(execution.logs) == 1
        assert execution.logs[0]["level"] == "INFO"
        assert execution.logs[0]["message"] == "Test log message"
        assert "timestamp" in execution.logs[0]

    def test_get_duration(self):
        """Test calculating execution duration."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # No duration before completion
        assert execution.get_duration() is None

        # Set start and end times
        execution.started_at = timezone.now()
        execution.completed_at = execution.started_at + timezone.timedelta(seconds=30)
        execution.save()

        duration = execution.get_duration()
        assert duration is not None
        assert "s" in duration

    def test_manager_for_task(self):
        """Test manager method for_task."""
        Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )
        Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=2,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        executions = Executions.objects.for_task(TaskType.BACKTEST, 1)
        assert executions.count() == 1
        assert executions.first().task_id == 1

    def test_manager_running(self):
        """Test manager method running."""
        Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )
        Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=2,
            execution_number=1,
            status=TaskStatus.COMPLETED,
        )

        running = Executions.objects.running()
        assert running.count() == 1
        assert running.first().status == TaskStatus.RUNNING
