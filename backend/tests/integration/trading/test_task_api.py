"""Integration tests for task-centric API endpoints."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import DataSource, LogLevel, TaskStatus, TradingMode
from apps.trading.models import BacktestTasks, StrategyConfigurations, TradingTasks
from apps.trading.models.logs import TaskLog, TaskMetric

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated API client."""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def strategy_config(test_user):
    """Create a test strategy configuration."""
    return StrategyConfigurations.objects.create(
        user=test_user,
        name="Test Strategy",
        strategy_type="floor",
        parameters={
            "entry_threshold": 0.5,
            "exit_threshold": 0.3,
        },
    )


@pytest.fixture
def oanda_account(test_user):
    """Create a test OANDA account."""
    from apps.market.models import OandaAccounts

    account = OandaAccounts.objects.create(
        user=test_user,
        account_id="TEST-001",
        api_type="practice",
        is_active=True,
    )
    account.set_api_token("test-api-key")
    account.save()
    return account


@pytest.fixture
def backtest_task(test_user, strategy_config):
    """Create a test backtest task."""
    return BacktestTasks.objects.create(
        user=test_user,
        config=strategy_config,
        name="Test Backtest",
        description="Test backtest task",
        data_source=DataSource.POSTGRESQL,
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now(),
        initial_balance=Decimal("10000.00"),
        commission_per_trade=Decimal("0.00"),
        instrument="USD_JPY",
        trading_mode=TradingMode.NETTING,
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def trading_task(test_user, strategy_config, oanda_account):
    """Create a test trading task."""
    return TradingTasks.objects.create(
        user=test_user,
        config=strategy_config,
        oanda_account=oanda_account,
        name="Test Trading",
        description="Test trading task",
        instrument="USD_JPY",
        trading_mode=TradingMode.NETTING,
        status=TaskStatus.CREATED,
    )


@pytest.mark.django_db
class TestBacktestTaskViewSet:
    """Test BacktestTaskViewSet endpoints."""

    def test_list_tasks(self, authenticated_client, backtest_task):
        """Test listing backtest tasks."""
        url = reverse("trading:backtest-task-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Test Backtest"

    def test_create_task(self, authenticated_client, strategy_config):
        """Test creating a backtest task."""
        url = reverse("trading:backtest-task-list")
        data = {
            "name": "New Backtest",
            "description": "New backtest task",
            "config": strategy_config.pk,
            "data_source": DataSource.POSTGRESQL,
            "start_time": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_time": timezone.now().isoformat(),
            "initial_balance": "10000.00",
            "commission_per_trade": "0.00",
            "instrument": "USD_JPY",
            "trading_mode": TradingMode.NETTING,
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Backtest"
        assert response.data["status"] == TaskStatus.CREATED

    def test_retrieve_task(self, authenticated_client, backtest_task):
        """Test retrieving a single backtest task."""
        url = reverse("trading:backtest-task-detail", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Backtest"
        assert response.data["id"] == backtest_task.pk

    def test_update_task(self, authenticated_client, backtest_task):
        """Test updating a backtest task."""
        url = reverse("trading:backtest-task-detail", kwargs={"pk": backtest_task.pk})
        data = {"description": "Updated description"}
        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["description"] == "Updated description"

    def test_delete_task(self, authenticated_client, backtest_task):
        """Test deleting a backtest task."""
        url = reverse("trading:backtest-task-detail", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BacktestTasks.objects.filter(pk=backtest_task.pk).exists()

    @patch("apps.trading.services.service.TaskServiceImpl.submit_task")
    def test_submit_task(self, mock_submit, authenticated_client, backtest_task):
        """Test submitting a task for execution."""
        # Mock the submit_task method to return the task with updated status
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.celery_task_id = str(uuid4())
        backtest_task.started_at = timezone.now()
        mock_submit.return_value = backtest_task

        url = reverse("trading:backtest-task-submit", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        assert response.data["celery_task_id"] is not None
        mock_submit.assert_called_once()

    def test_submit_task_invalid_status(self, authenticated_client, backtest_task):
        """Test submitting a task with invalid status."""
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        url = reverse("trading:backtest-task-submit", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "CREATED" in response.data["error"] or "status" in response.data["error"]

    @patch("apps.trading.services.service.TaskServiceImpl.cancel_task")
    def test_cancel_task(self, mock_cancel, authenticated_client, backtest_task):
        """Test stopping a running task."""
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.celery_task_id = str(uuid4())
        backtest_task.save()

        mock_cancel.return_value = True

        url = reverse("trading:backtest-task-stop", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        mock_cancel.assert_called_once()

    @patch("apps.trading.services.service.TaskServiceImpl.submit_task")
    def test_restart_task(self, mock_submit, authenticated_client, backtest_task):
        """Test restarting a task from beginning."""
        backtest_task.status = TaskStatus.COMPLETED
        backtest_task.save()

        # Mock the submit to return the task with running status
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.retry_count = 1
        mock_submit.return_value = backtest_task

        url = reverse("trading:backtest-task-restart", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        mock_submit.assert_called_once()

    @patch("apps.trading.services.service.TaskServiceImpl.submit_task")
    def test_resume_task(self, mock_submit, authenticated_client, backtest_task):
        """Test resuming a paused task."""
        backtest_task.status = TaskStatus.PAUSED
        backtest_task.save()

        # Mock the submit to return the task with running status
        backtest_task.status = TaskStatus.RUNNING
        mock_submit.return_value = backtest_task

        url = reverse("trading:backtest-task-resume", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        mock_submit.assert_called_once()

    def test_get_task_logs(self, authenticated_client, backtest_task):
        """Test retrieving task logs."""
        # Create some test logs
        TaskLog.objects.create(
            task=backtest_task,
            level=LogLevel.INFO,
            message="Test log message 1",
        )
        TaskLog.objects.create(
            task=backtest_task,
            level=LogLevel.ERROR,
            message="Test log message 2",
        )

        url = reverse("trading:backtest-task-logs", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_get_task_logs_with_filtering(self, authenticated_client, backtest_task):
        """Test retrieving task logs with level filtering."""
        TaskLog.objects.create(
            task=backtest_task,
            level=LogLevel.INFO,
            message="Info message",
        )
        TaskLog.objects.create(
            task=backtest_task,
            level=LogLevel.ERROR,
            message="Error message",
        )

        url = reverse("trading:backtest-task-logs", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url, {"level": "ERROR"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["level"] == LogLevel.ERROR

    def test_get_task_logs_with_pagination(self, authenticated_client, backtest_task):
        """Test retrieving task logs with pagination."""
        # Create multiple logs
        for i in range(15):
            TaskLog.objects.create(
                task=backtest_task,
                level=LogLevel.INFO,
                message=f"Log message {i}",
            )

        url = reverse("trading:backtest-task-logs", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url, {"limit": 10, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 10

        # Get next page
        response = authenticated_client.get(url, {"limit": 10, "offset": 10})
        assert len(response.data) == 5

    def test_get_task_metrics(self, authenticated_client, backtest_task):
        """Test retrieving task metrics."""
        # Create some test metrics
        TaskMetric.objects.create(
            task=backtest_task,
            metric_name="equity",
            metric_value=10500.0,
        )
        TaskMetric.objects.create(
            task=backtest_task,
            metric_name="drawdown",
            metric_value=0.05,
        )

        url = reverse("trading:backtest-task-metrics", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_get_task_metrics_with_filtering(self, authenticated_client, backtest_task):
        """Test retrieving task metrics with name filtering."""
        TaskMetric.objects.create(
            task=backtest_task,
            metric_name="equity",
            metric_value=10500.0,
        )
        TaskMetric.objects.create(
            task=backtest_task,
            metric_name="drawdown",
            metric_value=0.05,
        )

        url = reverse("trading:backtest-task-metrics", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url, {"metric_name": "equity"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["metric_name"] == "equity"

    def test_get_task_results(self, authenticated_client, backtest_task):
        """Test retrieving task results."""
        backtest_task.status = TaskStatus.COMPLETED
        backtest_task.result_data = {
            "total_trades": 100,
            "winning_trades": 60,
            "final_balance": 12000.0,
        }
        backtest_task.save()

        url = reverse("trading:backtest-task-results", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"]["total_trades"] == 100
        assert response.data["results"]["final_balance"] == 12000.0

    def test_get_task_results_not_completed(self, authenticated_client, backtest_task):
        """Test retrieving results for incomplete task."""
        url = reverse("trading:backtest-task-results", kwargs={"pk": backtest_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not completed" in response.data["error"]

    def test_authentication_required(self, api_client, backtest_task):
        """Test that authentication is required for all endpoints."""
        url = reverse("trading:backtest-task-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_can_only_see_own_tasks(
        self, authenticated_client, backtest_task, strategy_config
    ):
        """Test that users can only see their own tasks."""
        # Create another user and task
        other_user = User.objects.create_user(  # type: ignore[attr-defined]
            username="otheruser",
            email="other@example.com",
            password="otherpass123",
        )
        BacktestTasks.objects.create(
            user=other_user,
            config=strategy_config,
            name="Other User Task",
            data_source=DataSource.POSTGRESQL,
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now(),
            initial_balance=Decimal("10000.00"),
        )

        url = reverse("trading:backtest-task-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Test Backtest"


@pytest.mark.django_db
class TestTradingTaskViewSet:
    """Test TradingTaskViewSet endpoints."""

    def test_list_tasks(self, authenticated_client, trading_task):
        """Test listing trading tasks."""
        url = reverse("trading:trading-task-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Test Trading"

    def test_create_task(self, authenticated_client, strategy_config, oanda_account):
        """Test creating a trading task."""
        url = reverse("trading:trading-task-list")
        data = {
            "name": "New Trading",
            "description": "New trading task",
            "config": strategy_config.pk,
            "oanda_account": oanda_account.pk,
            "instrument": "USD_JPY",
            "trading_mode": TradingMode.NETTING,
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Trading"
        assert response.data["status"] == TaskStatus.CREATED

    def test_retrieve_task(self, authenticated_client, trading_task):
        """Test retrieving a single trading task."""
        url = reverse("trading:trading-task-detail", kwargs={"pk": trading_task.pk})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Trading"
        assert response.data["id"] == trading_task.pk

    def test_update_task(self, authenticated_client, trading_task):
        """Test updating a trading task."""
        url = reverse("trading:trading-task-detail", kwargs={"pk": trading_task.pk})
        data = {"description": "Updated description"}
        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["description"] == "Updated description"

    def test_delete_task(self, authenticated_client, trading_task):
        """Test deleting a trading task."""
        url = reverse("trading:trading-task-detail", kwargs={"pk": trading_task.pk})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not TradingTasks.objects.filter(pk=trading_task.pk).exists()

    @patch("apps.trading.services.service.TaskServiceImpl.submit_task")
    def test_submit_task(self, mock_submit, authenticated_client, trading_task):
        """Test submitting a task for execution."""
        trading_task.status = TaskStatus.RUNNING
        trading_task.celery_task_id = str(uuid4())
        trading_task.started_at = timezone.now()
        mock_submit.return_value = trading_task

        url = reverse("trading:trading-task-submit", kwargs={"pk": trading_task.pk})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.RUNNING
        mock_submit.assert_called_once()

    def test_authentication_required(self, api_client, trading_task):
        """Test that authentication is required for all endpoints."""
        url = reverse("trading:trading-task-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
