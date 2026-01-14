from __future__ import annotations

import importlib
from datetime import timedelta

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.trading.services.lock import TaskLockManager
from apps.trading.views import StrategyDefaultsView, StrategyView


class TestBacktestTaskStatusView:
    def _create_task_and_completed_execution(self, *, user):
        from django.utils import timezone

        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models import BacktestTask, StrategyConfig, TaskExecution

        config = StrategyConfig.objects.create(
            user=user,
            name="cfg-bt-status",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="",
        )
        now = timezone.now()
        task = BacktestTask.objects.create(
            user=user,
            config=config,
            name="bt-status",
            description="",
            data_source="postgresql",
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=2),
            status=TaskStatus.RUNNING,
        )
        TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.COMPLETED,
            progress=100,
            started_at=now - timedelta(days=2, minutes=5),
            completed_at=now - timedelta(days=2),
        )
        task.refresh_from_db()
        return task

    def test_recently_started_task_is_not_auto_completed(self, monkeypatch, test_user):
        from apps.trading.enums import TaskStatus
        from apps.trading.views import BacktestTaskStatusView

        task = self._create_task_and_completed_execution(user=test_user)

        # No lock info yet (Celery hasn't started), but task was updated recently.
        from apps.trading.services.lock import TaskLockManager

        monkeypatch.setattr(
            TaskLockManager,
            "get_lock_info",
            lambda *_args, **_kwargs: None,
        )

        factory = APIRequestFactory()
        req = factory.get(f"/api/trading/backtest-tasks/{task.pk}/status/")
        force_authenticate(req, user=test_user)
        resp = BacktestTaskStatusView.as_view()(req, task_id=task.pk)
        assert resp.status_code == 200
        data = resp.data

        assert data["status"] == TaskStatus.RUNNING
        assert data["pending_new_execution"] is True
        assert data["progress"] == 0

        assert isinstance(data.get("execution"), dict)
        assert data["execution"].get("id") is not None
        assert data["execution"].get("execution_number") == 1

    def test_old_stale_task_is_auto_completed(self, monkeypatch, test_user):
        from django.utils import timezone

        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTask
        from apps.trading.views import BacktestTaskStatusView

        task = self._create_task_and_completed_execution(user=test_user)

        # Make the RUNNING status look old so it can be treated as stale.
        BacktestTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        monkeypatch.setattr(
            TaskLockManager,
            "get_lock_info",
            lambda *_args, **_kwargs: None,
        )

        factory = APIRequestFactory()
        req = factory.get(f"/api/trading/backtest-tasks/{task.pk}/status/")
        force_authenticate(req, user=test_user)
        resp = BacktestTaskStatusView.as_view()(req, task_id=task.pk)
        assert resp.status_code == 200
        data = resp.data

        assert data["status"] == TaskStatus.COMPLETED
        assert data["pending_new_execution"] is False

        assert isinstance(data.get("execution"), dict)
        assert data["execution"].get("id") is not None
        assert data["execution"].get("execution_number") == 1


class TestTradingViews:
    def test_strategy_view_requires_auth(self):
        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/")
        resp = StrategyView.as_view()(req)
        assert resp.status_code in {401, 403}

    def test_strategy_view_sorts_by_name(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(
            registry_module.registry,
            "get_all_strategies_info",
            lambda: {
                "b": {"config_schema": {"display_name": "Beta"}, "description": ""},
                "a": {"config_schema": {"display_name": "Alpha"}, "description": ""},
            },
        )

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/")
        force_authenticate(req, user=test_user)

        resp = StrategyView.as_view()(req)
        assert resp.status_code == 200
        data = resp.data
        names = [s["name"] for s in data["strategies"]]
        assert names == ["Alpha", "Beta"]

    def test_strategy_defaults_view_requires_auth(self):
        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/floor/defaults/")
        resp = StrategyDefaultsView.as_view()(req, strategy_id="floor")
        assert resp.status_code in {401, 403}

    def test_strategy_defaults_view_returns_404_for_unknown_strategy(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(registry_module.registry, "is_registered", lambda _key: False)

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/nope/defaults/")
        force_authenticate(req, user=test_user)

        resp = StrategyDefaultsView.as_view()(req, strategy_id="nope")
        assert resp.status_code == 404

    def test_strategy_defaults_view_returns_defaults(self, monkeypatch, test_user):
        registry_module = importlib.import_module("apps.trading.services.registry")

        monkeypatch.setattr(registry_module.registry, "is_registered", lambda _key: True)
        monkeypatch.setattr(
            registry_module.registry,
            "get_all_strategies_info",
            lambda: {
                "floor": {
                    "config_schema": {
                        "properties": {
                            "instrument": {"type": "string"},
                            "max_layers": {"type": "integer"},
                        }
                    },
                    "description": "",
                }
            },
        )

        from django.conf import settings

        monkeypatch.setattr(
            settings,
            "TRADING_FLOOR_STRATEGY_DEFAULTS",
            {"instrument": "USD_JPY", "max_layers": 3, "extra": 123},
            raising=False,
        )

        factory = APIRequestFactory()
        req = factory.get("/api/trading/strategies/floor/defaults/")
        force_authenticate(req, user=test_user)

        resp = StrategyDefaultsView.as_view()(req, strategy_id="floor")
        assert resp.status_code == 200
        data = resp.data
        assert data["strategy_id"] == "floor"
        assert data["defaults"] == {"instrument": "USD_JPY", "max_layers": 3}
