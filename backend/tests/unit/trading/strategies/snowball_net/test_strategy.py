"""Unit tests for SnowballNet strategy behavior."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from apps.trading.dataclasses import EntryExecutionBinding, EventExecutionResult, Tick
from apps.trading.enums import EventType
from apps.trading.strategies.registry import registry
from apps.trading.strategies.snowball_net.config import SnowballNetConfig
from apps.trading.strategies.snowball_net.strategy import SnowballNetStrategy


def _tick(bid: str, ask: str) -> Tick:
    bid_dec = Decimal(bid)
    ask_dec = Decimal(ask)
    return Tick(
        instrument="USD_JPY",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        bid=bid_dec,
        ask=ask_dec,
        mid=(bid_dec + ask_dec) / Decimal("2"),
    )


def _state(strategy_state=None):
    return SimpleNamespace(strategy_state=strategy_state or {})


def test_snowball_net_registers_with_net_visualization_capability():
    assert registry.is_registered("snowball_net")
    capabilities = registry.capabilities(identifier="snowball_net")
    assert capabilities["runtime"]["hedging"] is False
    assert capabilities["runtime"]["netting"] is True
    assert capabilities["visualization"]["kind"] == "snowball_net"


def test_initial_entry_uses_net_position_merge_flags():
    strategy = SnowballNetStrategy("USD_JPY", Decimal("0.01"), SnowballNetConfig.from_dict({}))
    state = _state()

    result = strategy.on_tick(tick=_tick("149.99", "150.01"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.OPEN_POSITION
    assert event.strategy_type == "snowball_net"
    assert event.merge_with_existing is True
    assert event.strategy_event_type == "snowball_net_initial"
    assert result.state.strategy_state["pending_action"]["kind"] == "open"


def test_open_execution_updates_average_net_state():
    strategy = SnowballNetStrategy("USD_JPY", Decimal("0.01"), SnowballNetConfig.from_dict({}))
    state = _state()
    result = strategy.on_tick(tick=_tick("149.99", "150.01"), state=state)
    entry_id = result.state.strategy_state["pending_action"]["entry_id"]

    strategy.apply_event_execution_result(
        state=result.state,
        execution_result=EventExecutionResult(
            execution_price=Decimal("150.02"),
            executed_units=1000,
            entry_binding=EntryExecutionBinding(
                entry_id=entry_id,
                position_id="position-1",
                fill_price=Decimal("150.02"),
            ),
        ),
    )

    assert result.state.strategy_state["net_units"] == 1000
    assert result.state.strategy_state["average_price"] == "150.02"
    assert result.state.strategy_state["position_id"] == "position-1"
    assert result.state.strategy_state["pending_action"] == {}


def test_adverse_move_emits_add_against_average_price():
    strategy = SnowballNetStrategy("USD_JPY", Decimal("0.01"), SnowballNetConfig.from_dict({}))
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 1000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 0,
            "next_entry_id": 2,
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.68", "149.70"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.OPEN_POSITION
    assert event.strategy_event_type == "snowball_net_add"
    assert event.merge_with_existing is True
    assert event.actual_interval_pips == Decimal("30")


def test_profit_move_emits_force_instrument_partial_close():
    strategy = SnowballNetStrategy("USD_JPY", Decimal("0.01"), SnowballNetConfig.from_dict({}))
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 2000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 1,
            "next_entry_id": 3,
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("150.25", "150.27"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.CLOSE_POSITION
    assert event.strategy_event_type == "snowball_net_take_profit"
    assert event.force_instrument_close is True
    assert event.units == 1000
    assert event.close_reason == "net_take_profit"
