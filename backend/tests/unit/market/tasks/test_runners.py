"""Unit tests for task runners."""

from typing import Any
from unittest.mock import patch

import pytest

from apps.market.tasks import (
    publisher_runner,
    subscriber_runner,
    supervisor_runner,
)


class TestTaskRunners:
    """Test task runner instances."""

    def test_supervisor_runner_exists(self) -> None:
        """Test supervisor runner instance exists."""
        assert supervisor_runner is not None
        assert hasattr(supervisor_runner, "run")

    def test_publisher_runner_exists(self) -> None:
        """Test publisher runner instance exists."""
        assert publisher_runner is not None
        assert hasattr(publisher_runner, "run")

    def test_subscriber_runner_exists(self) -> None:
        """Test subscriber runner instance exists."""
        assert subscriber_runner is not None
        assert hasattr(subscriber_runner, "run")

    def test_runner_classes_importable(self) -> None:
        """Test that runner classes can be imported."""
        from apps.market.tasks import (
            BacktestTickPublisherRunner,
            TickPublisherRunner,
            TickSubscriberRunner,
            TickSupervisorRunner,
        )

        assert BacktestTickPublisherRunner is not None
        assert TickPublisherRunner is not None
        assert TickSubscriberRunner is not None
        assert TickSupervisorRunner is not None

    def test_backtest_task_function_importable(self) -> None:
        """Test that backtest task function can be imported."""
        from apps.market.tasks import publish_ticks_for_backtest

        assert publish_ticks_for_backtest is not None
        assert callable(publish_ticks_for_backtest)


@pytest.mark.django_db
class TestPublisherRunner:
    """Test TickPublisherRunner."""

    @patch("apps.market.tasks.publisher.redis_client")
    @patch("apps.market.tasks.publisher.CeleryTaskService")
    def test_publisher_runner_initialization(self, mock_service: Any, mock_redis: Any) -> None:
        """Test publisher runner can be initialized."""
        from apps.market.tasks.publisher import TickPublisherRunner

        runner = TickPublisherRunner()
        assert runner is not None
        assert runner.task_service is None
        assert runner.account is None


@pytest.mark.django_db
class TestSubscriberRunner:
    """Test TickSubscriberRunner."""

    @patch("apps.market.tasks.subscriber.redis_client")
    @patch("apps.market.tasks.subscriber.CeleryTaskService")
    def test_subscriber_runner_initialization(self, mock_service: Any, mock_redis: Any) -> None:
        """Test subscriber runner can be initialized."""
        from apps.market.tasks.subscriber import TickSubscriberRunner

        runner = TickSubscriberRunner()
        assert runner is not None
        assert runner.task_service is None
        assert len(runner.buffer) == 0


@pytest.mark.django_db
class TestBacktestPublisherRunner:
    """Test BacktestTickPublisherRunner."""

    def test_backtest_publisher_runner_initialization(self) -> None:
        """Test backtest publisher runner can be initialized."""
        from apps.market.tasks.backtest import BacktestTickPublisherRunner

        runner = BacktestTickPublisherRunner()
        assert runner is not None
        assert runner.task_service is None
