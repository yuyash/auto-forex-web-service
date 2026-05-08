"""Tests for trading order client id generation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from apps.trading.enums import Direction
from apps.trading.order_client_ids import TradingOrderClientIdFactory


def test_open_position_client_id_is_deterministic_and_oanda_safe():
    factory = TradingOrderClientIdFactory()
    task_id = uuid4()
    execution_id = uuid4()
    timestamp = datetime(2026, 5, 8, tzinfo=UTC)

    first = factory.open_position_id(
        task_id=task_id,
        execution_id=execution_id,
        instrument="EUR_USD",
        units=1000,
        direction=Direction.LONG,
        layer_index=1,
        retracement_count=0,
        tick_timestamp=timestamp,
        planned_exit_price=Decimal("1.1050"),
        stop_loss=Decimal("1.0950"),
    )
    second = factory.open_position_id(
        task_id=task_id,
        execution_id=execution_id,
        instrument="EUR_USD",
        units=1000,
        direction=Direction.LONG,
        layer_index=1,
        retracement_count=0,
        tick_timestamp=timestamp,
        planned_exit_price=Decimal("1.1050"),
        stop_loss=Decimal("1.0950"),
    )

    assert first == second
    assert first.startswith("af-EUR_USD-long-")
    assert len(first) <= 128
    assert " " not in first
