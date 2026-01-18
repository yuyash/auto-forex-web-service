"""Unit tests for execution models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.enums import TaskType
from apps.trading.models import Executions, TaskExecutionResult

User = get_user_model()


@pytest.mark.django_db
class TestTaskExecutionResultModel:
    """Test TaskExecutionResult model."""

    def test_create_task_execution_result(self):
        """Test creating task execution result."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

        result = TaskExecutionResult.objects.create(
            execution=execution,
            task_type=TaskType.BACKTEST,
            task_id=1,
            success=True,
        )

        assert result.execution == execution
        assert result.success is True
        assert result.task_type == TaskType.BACKTEST

    def test_task_execution_result_with_error(self):
        """Test task execution result with error."""
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
        )

        result = TaskExecutionResult.objects.create(
            execution=execution,
            task_type=TaskType.BACKTEST,
            task_id=1,
            success=False,
            error="Execution failed",
        )

        assert result.success is False
        assert result.error == "Execution failed"
