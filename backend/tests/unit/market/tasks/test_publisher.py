"""Unit tests for TickPublisherRunner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.market.tasks.publisher import TickPublisherRunner


class TestTickPublisherRunnerInit:
    """Tests for __init__."""

    def test_initial_attributes(self):
        runner = TickPublisherRunner()

        assert runner.task_service is None
        assert runner.account is None


class TestTickPublisherRunnerRun:
    """Tests for run method."""

    @patch("apps.market.tasks.publisher.redis_client")
    @patch("apps.market.tasks.publisher.acquire_lock", return_value=False)
    @patch("apps.market.tasks.publisher.current_task_id", return_value="task-1")
    @patch("apps.market.tasks.publisher.lock_value", return_value="worker-1")
    @patch("apps.market.tasks.publisher.CeleryTaskService")
    @patch("apps.market.tasks.publisher.settings")
    def test_run_already_locked_stops(
        self, mock_settings, MockService, mock_lock_val, mock_task_id, mock_acquire, mock_redis
    ):
        mock_settings.MARKET_REDIS_URL = "redis://localhost"
        mock_settings.MARKET_TICK_CHANNEL = "ticks"
        mock_settings.MARKET_TICK_PUBLISHER_LOCK_KEY = "lock:pub"

        svc_instance = MagicMock()
        svc_instance.should_stop.return_value = False
        MockService.return_value = svc_instance

        client = MagicMock()
        mock_redis.return_value = client

        runner = TickPublisherRunner()
        runner.run(account_id=1)

        svc_instance.mark_stopped.assert_called_once()

    @patch("apps.market.tasks.publisher.redis_client")
    @patch("apps.market.tasks.publisher.acquire_lock", return_value=True)
    @patch("apps.market.tasks.publisher.current_task_id", return_value="task-1")
    @patch("apps.market.tasks.publisher.lock_value", return_value="worker-1")
    @patch("apps.market.tasks.publisher.CeleryTaskService")
    @patch("apps.market.tasks.publisher.OandaAccounts")
    @patch("apps.market.tasks.publisher.settings")
    def test_run_account_not_found_stops(
        self,
        mock_settings,
        MockAccounts,
        MockService,
        mock_lock_val,
        mock_task_id,
        mock_acquire,
        mock_redis,
    ):
        mock_settings.MARKET_REDIS_URL = "redis://localhost"
        mock_settings.MARKET_TICK_CHANNEL = "ticks"
        mock_settings.MARKET_TICK_PUBLISHER_LOCK_KEY = "lock:pub"

        svc_instance = MagicMock()
        svc_instance.should_stop.return_value = False
        MockService.return_value = svc_instance

        MockAccounts.objects.filter.return_value.first.return_value = None

        client = MagicMock()
        mock_redis.return_value = client

        runner = TickPublisherRunner()
        runner.run(account_id=999)

        svc_instance.mark_stopped.assert_called_once()

    @patch("apps.market.tasks.publisher.redis_client")
    @patch("apps.market.tasks.publisher.acquire_lock", return_value=True)
    @patch("apps.market.tasks.publisher.current_task_id", return_value="task-1")
    @patch("apps.market.tasks.publisher.lock_value", return_value="worker-1")
    @patch("apps.market.tasks.publisher.CeleryTaskService")
    @patch("apps.market.tasks.publisher.settings")
    def test_run_stop_requested_immediately(
        self, mock_settings, MockService, mock_lock_val, mock_task_id, mock_acquire, mock_redis
    ):
        mock_settings.MARKET_REDIS_URL = "redis://localhost"
        mock_settings.MARKET_TICK_CHANNEL = "ticks"
        mock_settings.MARKET_TICK_PUBLISHER_LOCK_KEY = "lock:pub"

        svc_instance = MagicMock()
        svc_instance.should_stop.return_value = True
        MockService.return_value = svc_instance

        client = MagicMock()
        mock_redis.return_value = client

        runner = TickPublisherRunner()
        runner.run(account_id=1)

        svc_instance.mark_stopped.assert_called_once()


class TestValidateAccount:
    """Tests for _validate_account."""

    def test_returns_false_when_account_none(self):
        runner = TickPublisherRunner()
        runner.account = None
        runner.task_service = MagicMock()

        result = runner._validate_account(MagicMock(), "lock:key", 1)

        assert result is False

    @patch("apps.market.tasks.publisher.ApiType")
    def test_returns_false_for_non_live_account(self, MockApiType):
        MockApiType.LIVE = "live"

        runner = TickPublisherRunner()
        runner.account = MagicMock()
        runner.account.api_type = "practice"
        runner.task_service = MagicMock()

        result = runner._validate_account(MagicMock(), "lock:key", 1)

        assert result is False

    @patch("apps.market.tasks.publisher.ApiType")
    def test_returns_true_for_live_account(self, MockApiType):
        MockApiType.LIVE = "live"

        runner = TickPublisherRunner()
        runner.account = MagicMock()
        runner.account.api_type = "live"
        runner.task_service = MagicMock()

        result = runner._validate_account(MagicMock(), "lock:key", 1)

        assert result is True


class TestCleanupAndStop:
    """Tests for _cleanup_and_stop."""

    def test_deletes_lock_and_closes_client(self):
        runner = TickPublisherRunner()
        runner.task_service = MagicMock()

        client = MagicMock()
        runner._cleanup_and_stop(client, "lock:key", "done")

        client.delete.assert_called_once_with("lock:key")
        client.close.assert_called_once()

    def test_marks_stopped(self):
        runner = TickPublisherRunner()
        runner.task_service = MagicMock()

        runner._cleanup_and_stop(MagicMock(), "lock:key", "done")

        runner.task_service.mark_stopped.assert_called_once()

    def test_marks_failed_when_flag_set(self):
        from apps.market.models import CeleryTaskStatus

        runner = TickPublisherRunner()
        runner.task_service = MagicMock()

        runner._cleanup_and_stop(MagicMock(), "lock:key", "error", failed=True)

        call_kwargs = runner.task_service.mark_stopped.call_args.kwargs
        assert call_kwargs["status"] == CeleryTaskStatus.Status.FAILED

    def test_handles_client_errors_gracefully(self):
        runner = TickPublisherRunner()
        runner.task_service = MagicMock()

        client = MagicMock()
        client.delete.side_effect = Exception("redis down")
        client.close.side_effect = Exception("redis down")

        # Should not raise
        runner._cleanup_and_stop(client, "lock:key", "done")
        runner.task_service.mark_stopped.assert_called_once()
