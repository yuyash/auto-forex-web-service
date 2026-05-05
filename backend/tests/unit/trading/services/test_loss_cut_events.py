"""Unit tests for the loss-cut event loader."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.trading.enums import Direction, TaskType
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.loss_cut_events import load_loss_cut_events
from tests.integration.factories import BacktestTaskFactory


def _make_position(task, instrument: str = "USD_JPY") -> Position:
    return Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument=instrument,
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=False,
    )


def _make_trade(
    task,
    *,
    description: str,
    execution_method: str = "close_position",
    units: int = 1000,
    when: datetime | None = None,
    direction: Direction = Direction.LONG,
    position: Position | None = None,
):
    return Trade.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        timestamp=when or datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        direction=direction,
        units=units,
        instrument="USD_JPY",
        price=Decimal("150.000"),
        execution_method=execution_method,
        description=description,
        position=position,
    )


@pytest.mark.django_db
def test_load_loss_cut_events_returns_only_loss_cut_trades():
    task = BacktestTaskFactory()
    position = _make_position(task)

    _make_trade(task, description="SnowballNet take profit | units=1000", units=1000)
    loss_cut = _make_trade(
        task,
        description="SnowballNet loss cut | units=3000, avg=146.9, exit=145.5",
        units=3000,
        when=datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        position=position,
    )
    _make_trade(
        task,
        description="SnowballNet margin reduce | units=1000",
        when=datetime(2026, 1, 1, 3, 0, tzinfo=UTC),
    )

    events = load_loss_cut_events(
        task=task,
        task_type_label=TaskType.BACKTEST,
        execution_id=task.execution_id,
    )

    assert len(events) == 1
    assert events[0]["id"] == str(loss_cut.id)
    assert events[0]["units"] == 3000
    assert events[0]["direction"] == Direction.LONG.value
    assert events[0]["timestamp"].startswith("2026-01-01T02:00:00")
    assert events[0]["time"] == int(loss_cut.timestamp.timestamp())


@pytest.mark.django_db
def test_load_loss_cut_events_matches_stop_loss_descriptions():
    task = BacktestTaskFactory()

    _make_trade(
        task,
        description="[PROTECTION] stop_loss triggered | -120 pips",
        when=datetime(2026, 1, 1, 4, 0, tzinfo=UTC),
    )

    events = load_loss_cut_events(
        task=task,
        task_type_label=TaskType.BACKTEST,
        execution_id=task.execution_id,
    )
    assert len(events) == 1
    assert events[0]["units"] == 1000


@pytest.mark.django_db
def test_load_loss_cut_events_respects_time_range():
    task = BacktestTaskFactory()

    _make_trade(
        task,
        description="loss cut | out of range",
        when=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    in_range = _make_trade(
        task,
        description="loss cut | in range",
        when=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
    )

    events = load_loss_cut_events(
        task=task,
        task_type_label=TaskType.BACKTEST,
        execution_id=task.execution_id,
        since=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        until=datetime(2026, 1, 3, 0, 0, tzinfo=UTC),
    )
    assert [event["id"] for event in events] == [str(in_range.id)]


@pytest.mark.django_db
def test_load_loss_cut_events_orders_by_timestamp_ascending():
    task = BacktestTaskFactory()

    later = _make_trade(
        task,
        description="loss cut | late",
        when=datetime(2026, 1, 3, 0, 0, tzinfo=UTC),
    )
    earlier = _make_trade(
        task,
        description="loss cut | early",
        when=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
    )

    events = load_loss_cut_events(
        task=task,
        task_type_label=TaskType.BACKTEST,
        execution_id=task.execution_id,
    )
    assert [event["id"] for event in events] == [str(earlier.id), str(later.id)]
