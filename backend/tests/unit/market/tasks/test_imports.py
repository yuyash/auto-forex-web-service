"""Test that all tasks can be imported."""


class TestTaskImports:
    """Test task module imports."""

    def test_import_tasks_package(self) -> None:
        """Test importing tasks package."""
        from apps.market import tasks

        assert tasks is not None

    def test_import_all_tasks(self) -> None:
        """Test importing all task functions."""
        from apps.market.tasks import (
            ensure_tick_pubsub_running,
            publish_oanda_ticks,
            publish_ticks_for_backtest,
            subscribe_ticks_to_db,
        )

        assert ensure_tick_pubsub_running is not None
        assert publish_oanda_ticks is not None
        assert publish_ticks_for_backtest is not None
        assert subscribe_ticks_to_db is not None

    def test_tasks_are_celery_tasks(self) -> None:
        """Test that tasks are decorated as Celery tasks."""
        from apps.market.tasks import (
            ensure_tick_pubsub_running,
            publish_oanda_ticks,
            publish_ticks_for_backtest,
            subscribe_ticks_to_db,
        )

        # Check that tasks have Celery task attributes
        assert hasattr(ensure_tick_pubsub_running, "delay")
        assert hasattr(publish_oanda_ticks, "delay")
        assert hasattr(publish_ticks_for_backtest, "delay")
        assert hasattr(subscribe_ticks_to_db, "delay")

    def test_backward_compatibility(self) -> None:
        """Test backward compatibility with old import path."""
        # Old import should still work
        from apps.market.tasks import ensure_tick_pubsub_running

        # Verify it's a bound method
        assert hasattr(ensure_tick_pubsub_running, "delay")
        assert hasattr(ensure_tick_pubsub_running, "apply_async")
