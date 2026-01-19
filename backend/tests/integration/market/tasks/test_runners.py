"""Integration tests for task runners."""

import pytest

from apps.market.tasks import (
    backtest_publisher_runner,
    publisher_runner,
    subscriber_runner,
    supervisor_runner,
)


@pytest.mark.django_db
class TestTaskRunnersIntegration:
    """Integration tests for task runners."""

    def test_all_runners_have_run_method(self) -> None:
        """Test that all runners have run method."""
        assert hasattr(supervisor_runner, "run")
        assert hasattr(publisher_runner, "run")
        assert hasattr(subscriber_runner, "run")
        assert hasattr(backtest_publisher_runner, "run")

        # Verify they are callable
        assert callable(supervisor_runner.run)
        assert callable(publisher_runner.run)
        assert callable(subscriber_runner.run)
        assert callable(backtest_publisher_runner.run)

    def test_runners_are_celery_tasks(self) -> None:
        """Test that runner methods are decorated as Celery tasks."""
        # Check for Celery task attributes
        assert hasattr(supervisor_runner.run, "delay")
        assert hasattr(publisher_runner.run, "delay")
        assert hasattr(subscriber_runner.run, "delay")
        assert hasattr(backtest_publisher_runner.run, "delay")

    def test_runner_initialization_state(self) -> None:
        """Test that runners are properly initialized."""
        assert supervisor_runner.task_service is None
        assert publisher_runner.task_service is None
        assert publisher_runner.account is None
        assert subscriber_runner.task_service is None
        assert len(subscriber_runner.buffer) == 0
        assert backtest_publisher_runner.task_service is None
