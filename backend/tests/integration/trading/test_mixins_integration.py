"""Integration tests for TaskSubResourceMixin via BacktestTaskViewSet endpoints.

Tests the paginated sub-resource actions (metric-snapshots, logs, events,
trades, positions, orders) using real DB records and authenticated API calls.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import Direction, LogLevel, TaskType
from apps.trading.models import (
    BacktestTask,
    MetricSnapshot,
    Order,
    Position,
    TaskLog,
    Trade,
    TradingEvent,
)
from apps.trading.models.orders import OrderStatus, OrderType
from tests.integration.factories import (
    BacktestTaskFactory,
    StrategyConfigurationFactory,
    UserFactory,
)


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_task(user=None) -> BacktestTask:
    """Create a backtest task with a celery_task_id for sub-resource filtering."""
    if user is None:
        user = UserFactory()
    config = StrategyConfigurationFactory(user=user)
    task = BacktestTaskFactory(user=user, config=config, status="running")
    task.celery_task_id = "celery-test-id-123"
    task.save()
    return task


@pytest.mark.django_db
class TestMetricSnapshots:
    """GET /api/trading/tasks/backtest/{id}/metric_snapshots/"""

    def test_with_data(self):
        task = _make_task()
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            MetricSnapshot.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                celery_task_id=task.celery_task_id,
                timestamp=now + timedelta(minutes=i),
                margin_ratio=Decimal("0.05") + Decimal(str(i)) / 100,
                current_atr=Decimal("0.0012"),
            )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/metric_snapshots/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 3
        assert response.data["returned"] == 3
        assert len(response.data["snapshots"]) == 3

    def test_without_data(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/metric_snapshots/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 0
        assert response.data["returned"] == 0
        assert response.data["snapshots"] == []


@pytest.mark.django_db
class TestLogs:
    """GET /api/trading/tasks/backtest/{id}/logs/"""

    def test_with_logs(self):
        task = _make_task()
        client = _auth_client(task.user)

        for i in range(3):
            TaskLog.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                celery_task_id=task.celery_task_id,
                level=LogLevel.INFO,
                component="test",
                message=f"Log message {i}",
            )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3

    def test_without_logs(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestEvents:
    """GET /api/trading/tasks/backtest/{id}/events/"""

    def test_with_events(self):
        task = _make_task()
        client = _auth_client(task.user)

        for i in range(2):
            TradingEvent.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                celery_task_id=task.celery_task_id,
                event_type="initial_entry",
                severity="info",
                description=f"Event {i}",
                user=task.user,
                instrument="USD_JPY",
                details={"entry_id": i},
            )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/events/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_without_events(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/events/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestTrades:
    """GET /api/trading/tasks/backtest/{id}/trades/"""

    def test_with_trades(self):
        task = _make_task()
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        Trade.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            celery_task_id=task.celery_task_id,
            timestamp=now,
            direction=Direction.LONG,
            units=1000,
            instrument="USD_JPY",
            price=Decimal("150.500"),
            execution_method="initial_entry",
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/trades/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        trade = response.data["results"][0]
        assert trade["instrument"] == "USD_JPY"
        # Direction is normalized to buy/sell in the mixin
        assert trade["direction"] == "buy"

    def test_without_trades(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/trades/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestPositions:
    """GET /api/trading/tasks/backtest/{id}/positions/"""

    def test_with_positions(self):
        task = _make_task()
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        Position.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            celery_task_id=task.celery_task_id,
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("150.500"),
            entry_time=now,
            is_open=True,
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/positions/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        pos = response.data["results"][0]
        assert pos["instrument"] == "USD_JPY"
        assert pos["is_open"] is True

    def test_without_positions(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/positions/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestOrders:
    """GET /api/trading/tasks/backtest/{id}/orders/"""

    def test_with_orders(self):
        task = _make_task()
        client = _auth_client(task.user)

        Order.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            instrument="USD_JPY",
            order_type=OrderType.MARKET,
            direction=Direction.LONG,
            units=1000,
            fill_price=Decimal("150.500"),
            status=OrderStatus.FILLED,
            is_dry_run=True,
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        order = response.data["results"][0]
        assert order["instrument"] == "USD_JPY"
        assert order["status"] == "filled"

    def test_without_orders(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
