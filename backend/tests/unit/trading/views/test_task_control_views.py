"""Unit tests for task control endpoints."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.market.models import OandaAccounts
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTasks, Executions, StrategyConfigurations, TradingTasks

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db: None) -> User:  # type: ignore[type-arg]
    """Create test user."""
    return User.objects.create_user(    # type: ignore[attr-defined]
        username="testuser", password="testpass123"
    )


@pytest.fixture
def oanda_account(db, user):
    """Create test OANDA account."""
    return OandaAccounts.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        is_used=True,
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfigurations.objects.create(
        name="Test Strategy",
        strategy_type="floor",
        parameters={"test": "value"},
        user=user,
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create test backtest task."""
    return BacktestTasks.objects.create(
        name="Test Backtest",
        description="Test backtest task",
        config=strategy_config,
        user=user,
        instrument="EUR_USD",
        start_time=timezone.now(),
        end_time=timezone.now() + timedelta(days=1),
        status=TaskStatus.STOPPED,
    )


@pytest.fixture
def trading_task(db, user, strategy_config, oanda_account):
    """Create test trading task."""
    return TradingTasks.objects.create(
        name="Test Trading",
        description="Test trading task",
        config=strategy_config,
        user=user,
        oanda_account=oanda_account,
        instrument="EUR_USD",
        status=TaskStatus.STOPPED,
    )


@pytest.mark.django_db
class TestBacktestTaskStartView:
    """Tests for BacktestTaskStartView."""

    def test_start_returns_execution_id(self, api_client, user, backtest_task):
        """Test that start endpoint returns execution_id."""
        api_client.force_authenticate(user=user)

        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/start/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == backtest_task.pk

        # Verify execution was created
        if response.data["execution_id"]:
            execution = Executions.objects.get(pk=response.data["execution_id"])
            assert execution.task_type == TaskType.BACKTEST
            assert execution.task_id == backtest_task.pk

    def test_start_fails_when_already_running(self, api_client, user, backtest_task):
        """Test that start fails when task is already running."""
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/start/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestBacktestTaskResumeView:
    """Tests for BacktestTaskResumeView."""

    def test_resume_returns_execution_id(self, api_client, user, backtest_task):
        """Test that resume endpoint returns execution_id."""
        backtest_task.status = TaskStatus.STOPPED
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/resume/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == backtest_task.pk

    def test_resume_fails_when_running(self, api_client, user, backtest_task):
        """Test that resume fails when task is already running."""
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/resume/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestBacktestTaskRestartView:
    """Tests for BacktestTaskRestartView."""

    def test_restart_returns_execution_id(self, api_client, user, backtest_task):
        """Test that restart endpoint returns execution_id."""
        backtest_task.status = TaskStatus.STOPPED
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/restart/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == backtest_task.pk

    def test_restart_fails_when_running(self, api_client, user, backtest_task):
        """Test that restart fails when task is running."""
        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/backtest-tasks/{backtest_task.pk}/restart/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestBacktestTaskStatusView:
    """Tests for BacktestTaskStatusView."""

    def test_status_includes_execution_id_when_running(self, api_client, user, backtest_task):
        """Test that status includes execution_id when task is running."""
        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=0,
            started_at=timezone.now(),
        )

        backtest_task.status = TaskStatus.RUNNING
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/backtest-tasks/{backtest_task.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        assert "execution_id" in response.data
        assert response.data["execution_id"] == execution.pk
        assert response.data["status"] == TaskStatus.RUNNING

    def test_status_no_execution_id_when_stopped(self, api_client, user, backtest_task):
        """Test that status does not include execution_id when task is stopped."""
        backtest_task.status = TaskStatus.STOPPED
        backtest_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/backtest-tasks/{backtest_task.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        assert "execution_id" not in response.data or response.data.get("execution_id") is None
        assert response.data["status"] == TaskStatus.STOPPED


@pytest.mark.django_db
class TestTradingTaskStartView:
    """Tests for TradingTaskStartView."""

    def test_start_returns_execution_id(self, api_client, user, trading_task):
        """Test that start endpoint returns execution_id."""
        api_client.force_authenticate(user=user)

        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/start/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == trading_task.pk

        # Verify execution was created
        if response.data["execution_id"]:
            execution = Executions.objects.get(pk=response.data["execution_id"])
            assert execution.task_type == TaskType.TRADING
            assert execution.task_id == trading_task.pk

    def test_start_fails_when_already_running(self, api_client, user, trading_task):
        """Test that start fails when task is already running."""
        trading_task.status = TaskStatus.RUNNING
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/start/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestTradingTaskResumeView:
    """Tests for TradingTaskResumeView."""

    def test_resume_returns_execution_id(self, api_client, user, trading_task):
        """Test that resume endpoint returns execution_id."""
        trading_task.status = TaskStatus.STOPPED
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/resume/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == trading_task.pk

    def test_resume_fails_when_running(self, api_client, user, trading_task):
        """Test that resume fails when task is already running."""
        trading_task.status = TaskStatus.RUNNING
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/resume/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestTradingTaskRestartView:
    """Tests for TradingTaskRestartView."""

    def test_restart_returns_execution_id(self, api_client, user, trading_task):
        """Test that restart endpoint returns execution_id."""
        trading_task.status = TaskStatus.STOPPED
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/restart/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "execution_id" in response.data
        assert "task_id" in response.data
        assert "message" in response.data
        assert response.data["task_id"] == trading_task.pk

    def test_restart_fails_when_running(self, api_client, user, trading_task):
        """Test that restart fails when task is running."""
        trading_task.status = TaskStatus.RUNNING
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/trading/trading-tasks/{trading_task.pk}/restart/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.data


@pytest.mark.django_db
class TestTradingTaskStatusView:
    """Tests for TradingTaskStatusView."""

    def test_status_includes_execution_id_when_running(self, api_client, user, trading_task):
        """Test that status includes execution_id when task is running."""
        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=trading_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=0,
            started_at=timezone.now(),
        )

        trading_task.status = TaskStatus.RUNNING
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/trading-tasks/{trading_task.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        assert "execution_id" in response.data
        assert response.data["execution_id"] == execution.pk
        assert response.data["status"] == TaskStatus.RUNNING

    def test_status_no_execution_id_when_stopped(self, api_client, user, trading_task):
        """Test that status does not include execution_id when task is stopped."""
        trading_task.status = TaskStatus.STOPPED
        trading_task.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/trading-tasks/{trading_task.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        assert "execution_id" not in response.data or response.data.get("execution_id") is None
        assert response.data["status"] == TaskStatus.STOPPED


@pytest.mark.django_db
class TestErrorResponses:
    """Tests for error responses across all endpoints."""

    def test_start_returns_404_for_nonexistent_task(self, api_client, user):
        """Test that start returns 404 for nonexistent task."""
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/trading/backtest-tasks/99999/start/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_resume_returns_404_for_nonexistent_task(self, api_client, user):
        """Test that resume returns 404 for nonexistent task."""
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/trading/backtest-tasks/99999/resume/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_restart_returns_404_for_nonexistent_task(self, api_client, user):
        """Test that restart returns 404 for nonexistent task."""
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/trading/backtest-tasks/99999/restart/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_status_returns_404_for_nonexistent_task(self, api_client, user):
        """Test that status returns 404 for nonexistent task."""
        api_client.force_authenticate(user=user)

        response = api_client.get("/api/trading/backtest-tasks/99999/status/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
