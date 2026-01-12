from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.utils import timezone

from apps.trading.models import BacktestTask, StrategyConfig


class _FakeStrategy:
    def on_start(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []

    def on_tick(
        self, *, tick: dict[str, Any], state: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        _ = tick
        return state, []


class _FakePubSub:
    def __init__(self, *, calls: list[tuple[str, str]]):
        self._calls = calls
        self._request_id: str | None = None
        self._reads = 0

    def subscribe(self, channel: str) -> None:
        self._calls.append(("subscribe", channel))
        prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
        if channel.startswith(prefix):
            self._request_id = channel[len(prefix) :]

    def get_message(self, *, timeout: float | None = None) -> dict[str, Any] | None:
        _ = timeout
        # Emit a tick, then EOF, then go quiet.
        self._reads += 1
        rid = self._request_id or "unknown"
        if self._reads == 1:
            return {
                "type": "message",
                "data": json.dumps(
                    {
                        "type": "tick",
                        "request_id": rid,
                        "instrument": "USD_JPY",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "bid": "1.0",
                        "ask": "1.1",
                        "mid": "1.05",
                    }
                ),
            }
        if self._reads == 2:
            return {
                "type": "message",
                "data": json.dumps(
                    {
                        "type": "eof",
                        "request_id": rid,
                        "instrument": "USD_JPY",
                        "count": 1,
                    }
                ),
            }
        return None

    def close(self) -> None:
        return


class _FakeRedisClient:
    def __init__(self, *, calls: list[tuple[str, str]]):
        self._calls = calls
        self._pubsub = _FakePubSub(calls=calls)

    def pubsub(self, *, ignore_subscribe_messages: bool = True) -> _FakePubSub:
        _ = ignore_subscribe_messages
        return self._pubsub

    def close(self) -> None:
        return


@pytest.mark.django_db
def test_run_backtest_task_subscribes_before_enqueuing_publisher(monkeypatch, test_user):
    # Arrange
    calls: list[tuple[str, str]] = []

    import apps.market.tasks as market_tasks
    import apps.trading.tasks as trading_tasks
    from apps.trading.services import registry as strategy_registry_module

    monkeypatch.setattr(trading_tasks, "_ensure_strategies_registered", lambda: None)
    monkeypatch.setattr(trading_tasks, "_redis_client", lambda: _FakeRedisClient(calls=calls))
    monkeypatch.setattr(
        strategy_registry_module,
        "registry",
        type("FakeRegistry", (), {"create": lambda **_kwargs: _FakeStrategy()})(),
    )

    class _FakePublisher:
        @staticmethod
        def delay(**kwargs: Any) -> None:
            calls.append(("delay", str(kwargs.get("request_id") or "")))

    monkeypatch.setattr(market_tasks, "publish_ticks_for_backtest", _FakePublisher)

    config = StrategyConfig.objects.create(
        user=test_user,
        name="cfg-order",
        strategy_type="floor",
        parameters={"instrument": "USD_JPY"},
        description="",
    )

    now = timezone.now()
    task = BacktestTask.objects.create(
        user=test_user,
        config=config,
        name="bt-order",
        description="",
        data_source="postgresql",
        start_time=now - timedelta(minutes=2),
        end_time=now - timedelta(minutes=1),
    )

    # Act
    trading_tasks.run_backtest_task(task.id)  # type: ignore[attr-defined]

    # Assert: subscribe happens before delay, and both use the same request_id.
    assert len(calls) >= 2
    assert calls[0][0] == "subscribe"
    assert calls[1][0] == "delay"

    prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
    subscribed_channel = calls[0][1]
    assert subscribed_channel.startswith(prefix)
    subscribed_rid = subscribed_channel[len(prefix) :]
    delayed_rid = calls[1][1]
    assert subscribed_rid == delayed_rid
