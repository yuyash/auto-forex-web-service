"""Unit tests for execution API views.

Tests all execution-based endpoints with valid inputs, error responses,
filtering, pagination, and granularity parameters.

Requirements: 6.13, 6.14, 6.15, 6.16, 6.17, 6.18, 6.19, 6.20
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import (
    BacktestTasks,
    Executions,
    StrategyConfigurations,
    StrategyEvents,
    TradeLogs,
    TradingMetrics,
)

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db: None) -> User:  # type: ignore[type-arg]
    """Create test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfigurations.objects.create(
        user=user,  # Pass user instance, not user.pk
        name="Test Strategy",
        strategy_type="floor",
        parameters={"param1": "value1"},  # Changed from config to parameters
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create test backtest task."""
    return BacktestTasks.objects.create(
        user=user,
        name="Test Backtest",
        description="Test backtest task",
        config=strategy_config,  # Correct field name is 'config'
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=1),  # Correct field name is 'start_time'
        end_time=timezone.now(),  # Correct field name is 'end_time'
        initial_balance=Decimal("10000.00"),
    )


@pytest.fixture
def execution(db, backtest_task):
    """Create test execution."""
    return Executions.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=backtest_task.pk,
        execution_number=1,
        status=TaskStatus.COMPLETED,
        progress=100,
        started_at=timezone.now() - timedelta(hours=1),
        completed_at=timezone.now(),
        logs=[
            {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": "Test log message",
            }
        ],
    )


@pytest.fixture
def trading_metrics(db, execution):
    """Create test trading metrics."""
    metrics = []
    base_time = timezone.now() - timedelta(minutes=10)

    for i in range(5):
        metric = TradingMetrics.objects.create(
            execution=execution,
            sequence=i,
            timestamp=base_time + timedelta(minutes=i),
            realized_pnl=Decimal(str(100 + i * 10)),
            unrealized_pnl=Decimal(str(50 + i * 5)),
            total_pnl=Decimal(str(150 + i * 15)),
            open_positions=i % 3,
            total_trades=i + 1,
            tick_ask_min=Decimal("1.1000"),
            tick_ask_max=Decimal("1.1050"),
            tick_ask_avg=Decimal("1.1025"),
            tick_bid_min=Decimal("1.0990"),
            tick_bid_max=Decimal("1.1040"),
            tick_bid_avg=Decimal("1.1015"),
            tick_mid_min=Decimal("1.0995"),
            tick_mid_max=Decimal("1.1045"),
            tick_mid_avg=Decimal("1.1020"),
        )
        metrics.append(metric)

    return metrics


@pytest.fixture
def strategy_events(db, execution):
    """Create test strategy events."""
    events = []
    base_time = timezone.now() - timedelta(minutes=10)

    for i in range(3):
        event = StrategyEvents.objects.create(
            execution=execution,
            sequence=i,
            event_type="signal_generated",
            strategy_type="floor",
            timestamp=base_time + timedelta(minutes=i),
            event={"signal": "buy", "strength": 0.8},
        )
        events.append(event)

    return events


# ExecutionDetailView Tests (Requirements: 6.13)


@pytest.mark.django_db
class TestExecutionDetailView:
    """Test ExecutionDetailView endpoint."""

    def test_get_execution_detail_success(self, api_client, user, execution):
        """Test successful execution detail retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == execution.pk
        assert data["task_type"] == TaskType.BACKTEST
        assert data["status"] == TaskStatus.COMPLETED
        assert data["progress"] == 100
        assert "duration" in data
        assert "logs" in data

    def test_get_execution_detail_not_found(self, api_client, user):
        """Test execution detail with non-existent execution."""
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/trading/executions/99999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()

    def test_get_execution_detail_unauthorized(self, api_client, execution):
        """Test execution detail without authentication."""
        response = api_client.get(f"/api/trading/executions/{execution.pk}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_execution_detail_access_denied(self, api_client, execution):
        """Test execution detail with different user."""
        other_user = User.objects.create_user(  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ExecutionLogsView Tests (Requirements: 6.14)


@pytest.mark.django_db
class TestExecutionLogsView:
    """Test ExecutionLogsView endpoint."""

    def test_get_execution_logs_success(self, api_client, user, execution):
        """Test successful execution logs retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/logs/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) > 0
        assert data["execution_id"] == execution.pk

    def test_get_execution_logs_filter_by_level(self, api_client, user, execution):
        """Test execution logs filtering by level."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/logs/",
            {"level": "INFO"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for log in data["logs"]:
            assert log["level"] == "INFO"

    def test_get_execution_logs_with_limit(self, api_client, user, execution):
        """Test execution logs with limit parameter."""
        # Add more logs
        execution.logs = [
            {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": f"Log {i}",
            }
            for i in range(10)
        ]
        execution.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/logs/",
            {"limit": "5"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["logs"]) <= 5


# ExecutionStatusView Tests (Requirements: 6.15)


@pytest.mark.django_db
class TestExecutionStatusView:
    """Test ExecutionStatusView endpoint."""

    def test_get_execution_status_success(self, api_client, user, execution):
        """Test successful execution status retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["execution_id"] == execution.pk
        assert data["status"] == TaskStatus.COMPLETED
        assert data["progress"] == 100
        assert "started_at" in data
        assert "completed_at" in data

    def test_get_execution_status_running_with_estimate(self, api_client, user, backtest_task):
        """Test execution status for running execution with time estimate."""
        running_execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk,
            execution_number=2,
            status="running",
            progress=50,
            started_at=timezone.now() - timedelta(minutes=10),
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{running_execution.pk}/status/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "running"
        assert "estimated_remaining_seconds" in data


# ExecutionEventsView Tests (Requirements: 6.16)


@pytest.mark.django_db
class TestExecutionEventsView:
    """Test ExecutionEventsView endpoint."""

    def test_get_execution_events_success(self, api_client, user, execution, strategy_events):
        """Test successful execution events retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/events/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
        assert len(data["events"]) == 3
        assert data["execution_id"] == execution.pk

    def test_get_execution_events_filter_by_type(
        self, api_client, user, execution, strategy_events
    ):
        """Test execution events filtering by event_type."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/events/",
            {"event_type": "signal_generated"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for event in data["events"]:
            assert event["event_type"] == "signal_generated"

    def test_get_execution_events_since_sequence(
        self, api_client, user, execution, strategy_events
    ):
        """Test execution events with since_sequence parameter."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/events/",
            {"since_sequence": "1"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for event in data["events"]:
            assert event["sequence"] > 1


# ExecutionTradesView Tests (Requirements: 6.17)


@pytest.mark.django_db
class TestExecutionTradesView:
    """Test ExecutionTradesView endpoint."""

    def test_get_execution_trades_success(self, api_client, user, execution, trade_logs):
        """Test successful execution trades retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/trades/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "trades" in data
        assert len(data["trades"]) == 3
        assert data["execution_id"] == execution.pk

    def test_get_execution_trades_filter_by_instrument(
        self, api_client, user, execution, trade_logs
    ):
        """Test execution trades filtering by instrument."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/trades/",
            {"instrument": "EUR_USD"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for trade in data["trades"]:
            assert trade["trade"]["instrument"] == "EUR_USD"

    def test_get_execution_trades_filter_by_direction(
        self, api_client, user, execution, trade_logs
    ):
        """Test execution trades filtering by direction."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/trades/",
            {"direction": "long"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for trade in data["trades"]:
            assert trade["trade"]["direction"] == "long"


# ExecutionEquityView Tests (Requirements: 6.18)


@pytest.mark.django_db
class TestExecutionEquityView:
    """Test ExecutionEquityView endpoint."""

    def test_get_execution_equity_success(self, api_client, user, execution, trading_metrics):
        """Test successful execution equity retrieval with granularity."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/equity/",
            {"granularity": "60"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "bins" in data
        assert data["granularity_seconds"] == 60
        assert data["execution_id"] == execution.pk

    def test_get_execution_equity_invalid_granularity(self, api_client, user, execution):
        """Test execution equity with invalid granularity."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/equity/",
            {"granularity": "-1"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()

    def test_get_execution_equity_no_metrics(self, api_client, user, execution):
        """Test execution equity with no metrics."""
        # Delete all metrics
        TradingMetrics.objects.filter(execution=execution).delete()

        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/equity/",
            {"granularity": "60"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["bins"] == []
        assert data["count"] == 0

    def test_get_execution_equity_with_time_range(
        self, api_client, user, execution, trading_metrics
    ):
        """Test execution equity with time range filtering."""
        start_time = (timezone.now() - timedelta(minutes=8)).isoformat()
        end_time = (timezone.now() - timedelta(minutes=2)).isoformat()

        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/equity/",
            {
                "granularity": "60",
                "start_time": start_time,
                "end_time": end_time,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "bins" in data


# ExecutionMetricsView Tests (Requirements: 6.19)


@pytest.mark.django_db
class TestExecutionMetricsView:
    """Test ExecutionMetricsView endpoint."""

    def test_get_execution_metrics_raw(self, api_client, user, execution, trading_metrics):
        """Test execution metrics without granularity (raw data)."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/metrics/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "metrics" in data
        assert len(data["metrics"]) == 5
        assert data["execution_id"] == execution.pk

    def test_get_execution_metrics_with_granularity(
        self, api_client, user, execution, trading_metrics
    ):
        """Test execution metrics with granularity aggregation."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/metrics/",
            {"granularity": "60"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "metrics" in data
        assert data["granularity_seconds"] == 60

    def test_get_execution_metrics_last_n(self, api_client, user, execution, trading_metrics):
        """Test execution metrics with last_n parameter."""
        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/metrics/",
            {"last_n": "3"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["metrics"]) <= 3

    def test_get_execution_metrics_with_time_range(
        self, api_client, user, execution, trading_metrics
    ):
        """Test execution metrics with time range filtering."""
        start_time = (timezone.now() - timedelta(minutes=8)).isoformat()
        end_time = (timezone.now() - timedelta(minutes=2)).isoformat()

        api_client.force_authenticate(user=user)
        response = api_client.get(
            f"/api/trading/executions/{execution.pk}/metrics/",
            {
                "start_time": start_time,
                "end_time": end_time,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "metrics" in data


# ExecutionLatestMetricsView Tests (Requirements: 6.20)


@pytest.mark.django_db
class TestExecutionLatestMetricsView:
    """Test ExecutionLatestMetricsView endpoint."""

    def test_get_execution_latest_metrics_success(
        self, api_client, user, execution, trading_metrics
    ):
        """Test successful latest metrics retrieval."""
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/metrics/latest/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_metrics"] is True
        assert "metrics" in data
        assert data["metrics"]["sequence"] == 4  # Last sequence

    def test_get_execution_latest_metrics_no_metrics(self, api_client, user, execution):
        """Test latest metrics with no metrics available."""
        # Delete all metrics
        TradingMetrics.objects.filter(execution=execution).delete()

        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/trading/executions/{execution.pk}/metrics/latest/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_metrics"] is False
        assert data["metrics"] is None


@pytest.fixture
def trade_logs(db, execution):
    """Create test trade logs."""
    logs = []

    for i in range(3):
        log = TradeLogs.objects.create(
            execution=execution,
            sequence=i,
            trade={
                "instrument": "EUR_USD",
                "direction": "long" if i % 2 == 0 else "short",
                "units": 1000,
                "price": "1.1000",
                "pnl": str(10 + i),
            },
        )
        logs.append(log)

    return logs
