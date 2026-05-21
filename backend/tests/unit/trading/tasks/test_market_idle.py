"""Unit tests for market-aware idle transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.tasks.market_idle import MarketIdleCoordinator


class _FakeQuerySet:
    def __init__(self, task: "_FakeBacktestTask") -> None:
        self.task = task

    def update(self, **kwargs) -> int:
        if "status" in kwargs:
            self.task.status = kwargs["status"]
        return 1


class _FakeManager:
    task: "_FakeBacktestTask"

    def filter(self, **_kwargs) -> _FakeQuerySet:
        return _FakeQuerySet(self.task)


class _FakeBacktestTask:
    objects = _FakeManager()

    def __init__(self) -> None:
        self.pk = uuid4()
        self.status = TaskStatus.RUNNING
        self.market_idle_pre_close_minutes = 0
        self.market_idle_resume_delay_minutes = 0
        self.market_close_enabled = True
        self.market_close_weekday = 4
        self.market_close_hour_utc = 21
        self.market_open_weekday = 6
        self.market_open_hour_utc = 21
        self.holidays_enabled = False
        self.excluded_dates = []
        type(self).objects.task = self

    def refresh_from_db(self, **_kwargs) -> None:
        return None


class _FakeState:
    def __init__(self) -> None:
        self.last_tick_timestamp = None
        self.strategy_state = {}

    def save(self, **_kwargs) -> None:
        return None


def test_backtest_zero_delay_resumes_after_weekend_close() -> None:
    task = _FakeBacktestTask()
    loop = SimpleNamespace(
        last_delivered_tick_timestamp=datetime(2024, 6, 14, 21, 5, tzinfo=UTC),
        state=_FakeState(),
    )
    coordinator = MarketIdleCoordinator(task=task, task_type=TaskType.BACKTEST)

    coordinator.evaluate(loop)

    assert task.status == TaskStatus.IDLE

    loop.last_delivered_tick_timestamp = datetime(2024, 6, 16, 21, 1, tzinfo=UTC)
    coordinator.evaluate(loop)

    assert task.status == TaskStatus.RUNNING
    assert "_idle_entered_at" not in loop.state.strategy_state


def test_backtest_idles_during_custom_closed_window() -> None:
    task = _FakeBacktestTask()
    task.market_close_enabled = False
    task.excluded_dates = [
        {
            "start": "2024-12-24T16:59:00-05:00",
            "end": "2024-12-25T17:05:00-05:00",
            "timezone": "America/New_York",
        }
    ]
    loop = SimpleNamespace(
        last_delivered_tick_timestamp=datetime(2024, 12, 25, 12, 0, tzinfo=UTC),
        state=_FakeState(),
    )
    coordinator = MarketIdleCoordinator(task=task, task_type=TaskType.BACKTEST)

    coordinator.evaluate(loop)

    assert task.status == TaskStatus.IDLE

    loop.last_delivered_tick_timestamp = datetime(2024, 12, 25, 22, 6, tzinfo=UTC)
    coordinator.evaluate(loop)

    assert task.status == TaskStatus.RUNNING
