"""Integration tests for task runners."""

import pytest

from apps.market.tasks import (
    ensure_tick_pubsub_running,
    publish_oanda_ticks,
    publish_ticks_for_backtest,
    publisher_runner,
    subscribe_ticks_to_db,
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

        # Verify they are callable
        assert callable(supervisor_runner.run)
        assert callable(publisher_runner.run)
        assert callable(subscriber_runner.run)

    def test_runners_are_celery_tasks(self) -> None:
        """Test that task functions are decorated as Celery tasks."""
        # Verify they have Celery task attributes
        assert hasattr(ensure_tick_pubsub_running, "delay")
        assert hasattr(publish_oanda_ticks, "delay")
        assert hasattr(subscribe_ticks_to_db, "delay")
        assert hasattr(publish_ticks_for_backtest, "delay")

    def test_runner_initialization_state(self) -> None:
        """Test that runners are properly initialized."""
        assert supervisor_runner.task_service is None
        assert publisher_runner.task_service is None
        assert publisher_runner.account is None
        assert subscriber_runner.task_service is None
        assert len(subscriber_runner.buffer) == 0
