"""Integration tests for TaskSubResourceMixin via BacktestTaskViewSet endpoints.

Tests the paginated sub-resource actions (metrics, logs, events,
trades, positions, orders) using real DB records and authenticated API calls.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import Direction, LogLevel, TaskType
from apps.trading.models import (
    BacktestTask,
    CeleryTaskStatus,
    Metrics,
    Order,
    Position,
    StrategyEventRecord,
    TaskLog,
    TaskExecutionSnapshot,
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


def _make_task(user=None, *, strategy_type: str = "floor") -> BacktestTask:
    """Create a backtest task with an execution_id for sub-resource filtering."""
    if user is None:
        user = UserFactory()
    config = StrategyConfigurationFactory(user=user, strategy_type=strategy_type)
    task = cast(BacktestTask, BacktestTaskFactory(user=user, config=config, status="running"))
    from uuid import uuid4

    task.execution_id = uuid4()
    task.save()
    return task


@pytest.mark.django_db
class TestMetrics:
    """GET /api/trading/tasks/backtest/{id}/metrics/"""

    def test_with_data(self):
        task = _make_task()
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            Metrics.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                execution_id=task.execution_id,
                timestamp=now + timedelta(minutes=i),
                metrics={"margin_ratio": str(Decimal("0.05") + Decimal(str(i)) / 100)},
            )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3

    def test_without_data(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_interval_metrics_with_null_execution_id(self):
        task = _make_task()
        task.execution_id = None
        task.save(update_fields=["execution_id"])
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(2):
            Metrics.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                execution_id=None,
                timestamp=now + timedelta(minutes=i),
                metrics={"margin_ratio": str(Decimal("0.05") + Decimal(str(i)) / 100)},
            )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/metrics/",
            {"interval": 2, "page_size": 5000},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1


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
                execution_id=task.execution_id,
                level=LogLevel.INFO,
                component="test",
                message=f"Log message {i}",
            )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3
        assert "execution_id" in response.data["results"][0]

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
                execution_id=task.execution_id,
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
        assert "execution_id" in response.data["results"][0]

    def test_without_events(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/events/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_scope_filter_task_events(self):
        task = _make_task()
        client = _auth_client(task.user)

        TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="status_changed",
            severity="info",
            description="Task restart requested",
            user=task.user,
            instrument="USD_JPY",
            details={"kind": "task_restart_requested"},
        )
        TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="initial_entry",
            severity="info",
            description="Open long",
            user=task.user,
            instrument="USD_JPY",
            details={"event_type": "initial_entry"},
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/events/?scope=task")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["event_scope"] == "task"

    def test_scope_filter_trading_events(self):
        task = _make_task()
        client = _auth_client(task.user)

        TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="status_changed",
            severity="info",
            description="Task stop requested",
            user=task.user,
            instrument="USD_JPY",
            details={"kind": "task_stop_requested"},
        )
        TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="open_position",
            severity="info",
            description="Open long position",
            user=task.user,
            instrument="USD_JPY",
            details={"event_type": "initial_entry", "strategy_event_type": "initial_entry"},
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/events/?scope=trading")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["event_scope"] == "trading"

    def test_strategy_events_endpoint(self):
        task = _make_task(strategy_type="snowball")
        client = _auth_client(task.user)

        StrategyEventRecord.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            strategy_type="snowball",
            visual_group_id="group-1",
            root_entry_id=1,
            entry_id=1,
            basket="trend",
            direction="long",
            event_timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            event_type="open_position",
            severity="info",
            description="Initial entry",
            user=task.user,
            instrument="USD_JPY",
            details={"event_type": "open_position", "price": "150.100"},
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["strategy_type"] == "snowball"
        assert response.data["supported"] is True
        assert response.data["view_model"]["kind"] == "snowball_runs"
        assert len(response.data["view_model"]["groups"]) == 1
        assert response.data["view_model"]["groups"][0]["root_entry_id"] == 1

    def test_events_support_created_at_range_filter(self):
        task = _make_task()
        client = _auth_client(task.user)

        older = TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="initial_entry",
            severity="info",
            description="Older event",
            user=task.user,
            instrument="USD_JPY",
        )
        newer = TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            event_type="initial_entry",
            severity="info",
            description="Newer event",
            user=task.user,
            instrument="USD_JPY",
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/events/",
            {
                "created_from": older.created_at.isoformat(),
                "created_to": newer.created_at.isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/events/",
            {"created_from": newer.created_at.isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["description"] == "Newer event"

    def test_strategy_events_support_created_at_range_filter(self):
        task = _make_task(strategy_type="snowball")
        client = _auth_client(task.user)

        StrategyEventRecord.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            strategy_type="snowball",
            visual_group_id="group-1",
            root_entry_id=1,
            entry_id=1,
            basket="trend",
            direction="long",
            event_timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            event_type="open_position",
            severity="info",
            description="Older strategy event",
            user=task.user,
            instrument="USD_JPY",
            details={"event_type": "open_position"},
        )
        StrategyEventRecord.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            strategy_type="snowball",
            visual_group_id="group-2",
            root_entry_id=2,
            entry_id=2,
            basket="trend",
            direction="short",
            event_timestamp=datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc),
            event_type="open_position",
            severity="info",
            description="Newer strategy event",
            user=task.user,
            instrument="USD_JPY",
            details={"event_type": "open_position"},
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"root_entry_id": 2},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["supported"] is True
        assert len(response.data["view_model"]["groups"]) == 1
        assert response.data["view_model"]["groups"][0]["root_entry_id"] == 2


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
            execution_id=task.execution_id,
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

    def test_trades_support_timestamp_range_filter(self):
        task = _make_task()
        client = _auth_client(task.user)
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        Trade.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=now,
            direction=Direction.LONG,
            units=1000,
            instrument="USD_JPY",
            price=Decimal("150.500"),
            execution_method="initial_entry",
        )
        Trade.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=now + timedelta(minutes=5),
            direction=Direction.SHORT,
            units=1000,
            instrument="USD_JPY",
            price=Decimal("150.700"),
            execution_method="take_profit",
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/trades/",
            {"timestamp_from": (now + timedelta(minutes=1)).isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["direction"] == "sell"


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
            execution_id=task.execution_id,
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
            execution_id=task.execution_id,
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
        assert "execution_id" not in order

    def test_without_orders(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestExecutions:
    """GET /api/trading/tasks/backtest/{id}/executions/"""

    def test_with_execution_history(self):
        task = _make_task()
        client = _auth_client(task.user)
        from uuid import uuid4

        # Create a completed past execution
        old_execution_id = uuid4()
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key=f"{task.pk}:{old_execution_id}",
            status=CeleryTaskStatus.Status.COMPLETED,
        )

        # Set up current execution
        new_execution_id = uuid4()
        task.execution_id = new_execution_id
        task.status = "running"
        task.save(update_fields=["execution_id", "status", "updated_at"])

        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key=f"{task.pk}:{new_execution_id}",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/executions/?include_metrics=true"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        ids = {r["id"] for r in response.data["results"]}
        assert str(new_execution_id) in ids
        assert str(old_execution_id) in ids
        current = next(r for r in response.data["results"] if r["id"] == str(new_execution_id))
        assert current["status"] == "running"
        assert "metrics" in current

    def test_paginate_before_metric_aggregation_and_get_single_execution(self):
        task = _make_task()
        client = _auth_client(task.user)
        from uuid import uuid4

        execution_ids = [uuid4(), uuid4(), uuid4()]
        for execution_id in execution_ids:
            CeleryTaskStatus.objects.create(
                task_name="trading.tasks.run_backtest_task",
                instance_key=f"{task.pk}:{execution_id}",
                status=CeleryTaskStatus.Status.COMPLETED,
            )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/executions/",
            {"page": 1, "page_size": 1, "include_metrics": "true"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 4
        assert len(response.data["results"]) == 1
        execution_id = response.data["results"][0]["id"]
        assert "metrics" in response.data["results"][0]

        detail_response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/executions/{execution_id}/",
            {"include_metrics": "true"},
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["id"] == execution_id
        assert "metrics" in detail_response.data

        missing_response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/executions/{uuid4()}/",
        )
        assert missing_response.status_code == status.HTTP_404_NOT_FOUND

    def test_execution_detail_prefers_persisted_snapshot(self):
        task = _make_task()
        client = _auth_client(task.user)
        from uuid import uuid4

        execution_id = uuid4()
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key=f"{task.pk}:{execution_id}",
            status=CeleryTaskStatus.Status.COMPLETED,
        )
        TaskExecutionSnapshot.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=execution_id,
            summary={
                "timestamp": "2026-03-21T00:00:00+00:00",
                "pnl": {"realized": "12.5", "unrealized": "0"},
                "counts": {
                    "total_trades": 7,
                    "open_positions": 0,
                    "closed_positions": 3,
                },
                "execution": {
                    "current_balance": "10012.5",
                    "ticks_processed": 42,
                    "account_currency": "USD",
                    "current_balance_display": "10012.5",
                    "display_currency": "USD",
                },
                "tick": {
                    "timestamp": "2026-03-21T00:00:00+00:00",
                    "bid": "150.1000",
                    "ask": "150.1100",
                    "mid": "150.1050",
                },
                "task": {
                    "status": "completed",
                    "started_at": None,
                    "completed_at": "2026-03-21T00:00:10+00:00",
                    "error_message": None,
                    "progress": 100,
                },
            },
            metrics={
                "total_pnl": "12.5",
                "unrealized_pnl": "0",
                "total_trades": 7,
                "winning_trades": 5,
                "losing_trades": 2,
                "win_rate": "71.4286",
            },
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/executions/{execution_id}/",
            {"include_metrics": "true"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["metrics"]["total_trades"] == 7
        assert response.data["metrics"]["winning_trades"] == 5


@pytest.mark.django_db
class TestTrendReplay:
    """GET /api/trading/tasks/backtest/{id}/trend-replay/"""

    def test_returns_windowed_trades_and_positions(self):
        task = _make_task()
        client = _auth_client(task.user)
        base_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        position = Position.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction="long",
            units=1000,
            entry_price=Decimal("150.000"),
            entry_time=base_time,
            is_open=True,
        )
        trade = Trade.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction="long",
            units=1000,
            price=Decimal("150.010"),
            execution_method="market_entry",
            timestamp=base_time + timedelta(minutes=1),
            position=position,
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/trend-replay/",
            {
                "range_from": base_time.isoformat(),
                "range_to": (base_time + timedelta(minutes=2)).isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["meta"]["mode"] == "windowed"
        assert response.data["meta"]["returned_trades"] == 1
        assert len(response.data["trades"]) == 1
        assert len(response.data["positions"]) == 1
        assert len(response.data["trade_markers"]) == 1
        assert response.data["trades"][0]["id"] == str(trade.id)
        assert response.data["positions"][0]["trade_ids"] == [str(trade.id)]
