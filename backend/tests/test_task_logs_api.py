"""
Unit tests for task logs API endpoints.

Tests the logs API endpoints for both BacktestTask and TradingTask including:
- Pagination with various limit/offset combinations
- Filtering by execution_id and level
- Empty results handling
- Unauthorized access

Requirements: 1.4, 6.1, 6.2, 6.3, 6.4, 6.5
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus, TaskType
from trading.execution_models import TaskExecution
from trading.models import StrategyConfig
from trading.trading_task_models import TradingTask

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfig.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="MA_CROSSOVER",
        parameters={
            "fast_period": 10,
            "slow_period": 20,
        },
    )


@pytest.fixture
def backtest_task_with_logs(db, user, strategy_config):
    """Create backtest task with execution logs."""
    from datetime import timedelta

    task = BacktestTask.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        description="Test backtest task",
        status=TaskStatus.COMPLETED,
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=7),
        end_time=timezone.now() - timedelta(days=1),
    )

    # Create execution with logs
    execution = TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.COMPLETED,
        logs=[
            {
                "timestamp": "2025-01-15T10:00:00Z",
                "level": "INFO",
                "message": "Starting backtest",
            },
            {
                "timestamp": "2025-01-15T10:05:00Z",
                "level": "INFO",
                "message": "Processing data",
            },
            {
                "timestamp": "2025-01-15T10:10:00Z",
                "level": "WARNING",
                "message": "Low liquidity detected",
            },
            {
                "timestamp": "2025-01-15T10:15:00Z",
                "level": "ERROR",
                "message": "Failed to fetch data",
            },
            {
                "timestamp": "2025-01-15T10:20:00Z",
                "level": "INFO",
                "message": "Backtest completed",
            },
        ],
    )

    return task, execution


@pytest.fixture
def oanda_account(db, user):
    """Create test OANDA account."""
    from accounts.models import OandaAccount

    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        currency="USD",
    )
    account.set_api_token("test_token_12345")
    account.save()
    return account


@pytest.fixture
def trading_task_with_logs(db, user, strategy_config, oanda_account):
    """Create trading task with execution logs."""
    task = TradingTask.objects.create(
        user=user,
        config=strategy_config,
        oanda_account=oanda_account,
        name="Test Trading",
        description="Test trading task",
        status=TaskStatus.STOPPED,
    )

    # Create execution with logs
    execution = TaskExecution.objects.create(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.COMPLETED,
        logs=[
            {
                "timestamp": "2025-01-15T11:00:00Z",
                "level": "INFO",
                "message": "Starting trading",
            },
            {
                "timestamp": "2025-01-15T11:05:00Z",
                "level": "INFO",
                "message": "Monitoring market",
            },
        ],
    )

    return task, execution


@pytest.mark.django_db
class TestBacktestTaskLogsAPI:
    """Test BacktestTask logs API endpoint."""

    def test_get_logs_success(self, api_client, user, backtest_task_with_logs):
        """Test successful retrieval of backtest task logs."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 5
        assert len(response.data["results"]) == 5
        assert response.data["results"][0]["execution_number"] == 1

    def test_get_logs_with_pagination(self, api_client, user, backtest_task_with_logs):
        """Test logs retrieval with pagination."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"limit": 2, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 5
        assert len(response.data["results"]) == 2
        assert response.data["next"] is not None
        assert response.data["previous"] is None

    def test_get_logs_with_level_filter(self, api_client, user, backtest_task_with_logs):
        """Test logs retrieval with level filter."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"level": "ERROR"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["level"] == "ERROR"

    def test_get_logs_with_execution_id_filter(self, api_client, user, backtest_task_with_logs):
        """Test logs retrieval with execution_id filter."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"execution_id": execution.pk})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 5
        assert all(log["execution_id"] == execution.pk for log in response.data["results"])

    def test_get_logs_empty_results(self, api_client, user, strategy_config):
        """Test logs retrieval with no logs."""
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name="Empty Task",
            status=TaskStatus.CREATED,
            instrument="EUR_USD",
            start_time=timezone.now(),
            end_time=timezone.now(),
        )
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert len(response.data["results"]) == 0

    def test_get_logs_unauthorized(self, api_client, backtest_task_with_logs):
        """Test logs retrieval without authentication."""
        task, execution = backtest_task_with_logs

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_logs_wrong_user(self, api_client, other_user, backtest_task_with_logs):
        """Test logs retrieval by different user."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=other_user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_logs_invalid_limit(self, api_client, user, backtest_task_with_logs):
        """Test logs retrieval with invalid limit parameter."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"limit": "invalid"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_logs_invalid_execution_id(self, api_client, user, backtest_task_with_logs):
        """Test logs retrieval with invalid execution_id parameter."""
        task, execution = backtest_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"execution_id": "invalid"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTradingTaskLogsAPI:
    """Test TradingTask logs API endpoint."""

    def test_get_logs_success(self, api_client, user, trading_task_with_logs):
        """Test successful retrieval of trading task logs."""
        task, execution = trading_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:trading_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_get_logs_with_pagination(self, api_client, user, trading_task_with_logs):
        """Test logs retrieval with pagination."""
        task, execution = trading_task_with_logs
        api_client.force_authenticate(user=user)

        url = reverse("trading:trading_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url, {"limit": 1, "offset": 0})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 1
        assert response.data["next"] is not None

    def test_get_logs_unauthorized(self, api_client, trading_task_with_logs):
        """Test logs retrieval without authentication."""
        task, execution = trading_task_with_logs

        url = reverse("trading:trading_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_logs_wrong_user(self, api_client, other_user, trading_task_with_logs):
        """Test logs retrieval by different user."""
        task, execution = trading_task_with_logs
        api_client.force_authenticate(user=other_user)

        url = reverse("trading:trading_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
