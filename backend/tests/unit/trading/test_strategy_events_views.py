from __future__ import annotations

from datetime import timedelta

from rest_framework.test import APIRequestFactory, force_authenticate


class TestBacktestTaskStrategyEventsView:
    def test_strategy_events_return_db_rows_1_to_1(self, test_user):
        from django.utils import timezone

        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models import (
            BacktestTask,
            ExecutionStrategyEvent,
            StrategyConfig,
            TaskExecution,
        )
        from apps.trading.views import BacktestTaskStrategyEventsView

        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-bt-events",
            strategy_type="floor",
            parameters={"instrument": "USD_JPY"},
            description="",
        )
        now = timezone.now()
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            name="bt-events",
            description="",
            data_source="postgresql",
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=2),
            status=TaskStatus.COMPLETED,
        )
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.COMPLETED,
            progress=100,
            started_at=now - timedelta(days=2, minutes=5),
            completed_at=now - timedelta(days=2),
        )

        e0 = {
            "event_type": "initial_entry",
            "timestamp": "2025-01-01T00:00:00Z",
            "layer_number": 1,
            "direction": "long",
            "units": 1000,
            "entry_price": 1.1,
            "price": 1.1,
            "retracement_count": 0,
        }
        e1 = {
            "event_type": "retracement",
            "timestamp": "2025-01-01T00:01:00Z",
            "layer_number": 1,
            "direction": "long",
            "units": 1500,
            "entry_price": 1.09,
            "price": 1.09,
            "retracement_count": 1,
        }
        e2 = {
            "event_type": "take_profit",
            "timestamp": "2025-01-01T00:02:00Z",
            "layer_number": 1,
            "direction": "long",
            "units": 1000,
            "exit_price": 1.11,
            "pnl": 12.34,
        }

        # Deliberately insert out-of-order sequences; API should return by (sequence, id).
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=2, event_type="take_profit", event=e2
        )
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=0, event_type="initial_entry", event=e0
        )
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=1, event_type="retracement", event=e1
        )

        factory = APIRequestFactory()
        req = factory.get(f"/api/trading/backtest-tasks/{task.pk}/strategy-events/")
        force_authenticate(req, user=test_user)
        resp = BacktestTaskStrategyEventsView.as_view()(req, task_id=task.pk)
        assert resp.status_code == 200
        data = resp.data

        assert isinstance(data.get("strategy_events"), list)
        events = data["strategy_events"]
        assert events == [e0, e1, e2]
        assert data["has_metrics"] is True
        assert data["count"] == 3

    def test_strategy_events_paginates(self, test_user):
        from django.utils import timezone

        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models import (
            BacktestTask,
            ExecutionStrategyEvent,
            StrategyConfig,
            TaskExecution,
        )
        from apps.trading.views import BacktestTaskStrategyEventsView

        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-bt-events-page",
            strategy_type="floor",
            parameters={"instrument": "USD_JPY"},
            description="",
        )
        now = timezone.now()
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            name="bt-events-page",
            description="",
            data_source="postgresql",
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=2),
            status=TaskStatus.COMPLETED,
        )
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.COMPLETED,
            progress=100,
            started_at=now - timedelta(days=2, minutes=5),
            completed_at=now - timedelta(days=2),
        )

        e0 = {"event_type": "initial_entry", "timestamp": "2025-01-01T00:00:00Z", "price": 1.1}
        e1 = {"event_type": "retracement", "timestamp": "2025-01-01T00:01:00Z", "price": 1.09}
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=0, event_type="initial_entry", event=e0
        )
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=1, event_type="retracement", event=e1
        )

        factory = APIRequestFactory()
        req = factory.get(
            f"/api/trading/backtest-tasks/{task.pk}/strategy-events/?page=1&page_size=1"
        )
        force_authenticate(req, user=test_user)
        resp = BacktestTaskStrategyEventsView.as_view()(req, task_id=task.pk)
        assert resp.status_code == 200
        data = resp.data
        assert data["count"] == 2
        assert len(data["strategy_events"]) == 1
        assert data["strategy_events"][0]["event_type"] == "initial_entry"
        assert data["next"] is not None


class TestTradingTaskStrategyEventsView:
    def test_trading_strategy_events_return_db_rows_1_to_1(self, test_user):
        from django.utils import timezone

        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models import (
            ExecutionStrategyEvent,
            StrategyConfig,
            TaskExecution,
            TradingTask,
        )
        from apps.trading.views import TradingTaskStrategyEventsView
        from apps.market.models import OandaAccount

        oanda_account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-36034971-001",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            is_active=True,
        )

        config = StrategyConfig.objects.create(
            user=test_user,
            name="cfg-tt-events",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        task = TradingTask.objects.create(
            user=test_user,
            config=config,
            oanda_account=oanda_account,
            name="tt-events",
            description="",
            status=TaskStatus.STOPPED,
        )
        now = timezone.now()
        execution = TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.STOPPED,
            progress=100,
            started_at=now - timedelta(minutes=10),
            completed_at=now,
        )

        e0 = {"event_type": "initial_entry", "timestamp": "2025-01-01T00:00:00Z", "price": 1.1}
        e1 = {
            "event_type": "take_profit",
            "timestamp": "2025-01-01T00:02:00Z",
            "exit_price": 1.11,
            "pnl": 1.23,
        }
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=0, event_type="initial_entry", event=e0
        )
        ExecutionStrategyEvent.objects.create(
            execution=execution, sequence=1, event_type="take_profit", event=e1
        )

        factory = APIRequestFactory()
        req = factory.get(f"/api/trading/trading-tasks/{task.pk}/strategy-events/")
        force_authenticate(req, user=test_user)
        resp = TradingTaskStrategyEventsView.as_view()(req, task_id=task.pk)
        assert resp.status_code == 200
        data = resp.data
        assert data["strategy_events"] == [e0, e1]
        assert data["has_metrics"] is True
