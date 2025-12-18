"""Shared fixtures for trading integration tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_trading_celery_tasks(monkeypatch):
    """Prevent integration tests from enqueuing real Celery jobs."""

    class _DummyAsyncResult:  # minimal stand-in
        id = "test-task-id"

    def _dummy_delay(*_args, **_kwargs):
        return _DummyAsyncResult()

    # Patch lazily-imported Celery tasks used by views.
    import apps.trading.tasks as trading_tasks

    for task_name in [
        "run_trading_task",
        "stop_trading_task",
        "run_backtest_task",
        "stop_backtest_task",
    ]:
        if hasattr(trading_tasks, task_name):
            task_obj = getattr(trading_tasks, task_name)
            monkeypatch.setattr(task_obj, "delay", _dummy_delay, raising=False)


@pytest.fixture(autouse=True)
def _stub_live_results_redis(monkeypatch):
    """Avoid requiring a real Redis instance for live-results endpoints."""

    from apps.trading.services.performance import LivePerformanceService

    class _DummyRedis:
        def __init__(self):
            self._store: dict[str, str] = {}

        def setex(self, key, _ttl_seconds, value):
            self._store[str(key)] = str(value)

        def get(self, key):
            return self._store.get(str(key))

    dummy = _DummyRedis()
    monkeypatch.setattr(LivePerformanceService, "_redis_client", staticmethod(lambda: dummy))


@pytest.fixture
def oanda_account(db, test_user):
    """Create an active OANDA account owned by the test user."""

    from apps.market.models import OandaAccount

    account = OandaAccount.objects.create(
        user=test_user,
        account_id="101-001-0000000-001",
        api_token="",
        api_type="practice",
        jurisdiction="OTHER",
        currency="USD",
        is_active=True,
        is_default=True,
    )
    account.set_api_token("token")
    account.save(update_fields=["api_token"])
    return account
