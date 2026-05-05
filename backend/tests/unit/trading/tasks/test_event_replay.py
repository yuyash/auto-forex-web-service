"""Unit tests for trading event replay idempotency helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from apps.trading.enums import EventType, TaskType
from apps.trading.events import ClosePositionEvent, OpenPositionEvent
from apps.trading.tasks.event_replay import event_already_applied


def _executor():
    return SimpleNamespace(
        task_type=TaskType.TRADING,
        task=SimpleNamespace(pk=uuid4(), execution_id=uuid4()),
        instrument="USD_JPY",
    )


def test_snowball_net_replayed_open_is_skipped_after_broker_reconciliation():
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    state = SimpleNamespace(
        strategy_state={
            "last_action": {
                "kind": "reconciled",
                "action": "open",
                "entry_id": 2,
                "units": 1000,
                "timestamp": timestamp.isoformat(),
            }
        }
    )
    event = OpenPositionEvent(
        event_type=EventType.OPEN_POSITION,
        timestamp=timestamp,
        layer_number=1,
        direction="long",
        price=Decimal("150.00"),
        units=1000,
        entry_id=2,
        strategy_event_type="snowball_net_add",
    )

    assert event_already_applied(
        _executor(),
        trading_event=SimpleNamespace(details=event.to_dict()),
        state=state,
    )


def test_snowball_net_replayed_close_is_skipped_after_broker_reconciliation():
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    state = SimpleNamespace(
        strategy_state={
            "last_action": {
                "kind": "reconciled",
                "action": "close",
                "units": 1000,
                "timestamp": timestamp.isoformat(),
            }
        }
    )
    event = ClosePositionEvent(
        event_type=EventType.CLOSE_POSITION,
        timestamp=timestamp,
        layer_number=1,
        direction="long",
        entry_price=Decimal("150.00"),
        exit_price=Decimal("150.20"),
        units=1000,
        position_id="position-1",
        strategy_event_type="snowball_net_take_profit",
        force_instrument_close=True,
    )

    assert event_already_applied(
        _executor(),
        trading_event=SimpleNamespace(details=event.to_dict()),
        state=state,
    )
