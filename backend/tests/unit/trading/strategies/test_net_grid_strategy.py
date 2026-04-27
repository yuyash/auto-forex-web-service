"""Unit tests for the Net Grid strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from apps.trading.dataclasses import EntryExecutionBinding, EventExecutionResult
from apps.trading.dataclasses.tick import Tick
from apps.trading.events import ClosePositionEvent, OpenPositionEvent
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.net_grid.models import NetGridConfig
from apps.trading.strategies.net_grid.strategy import NetGridStrategy


def _state(*, ticks_processed: int = 0, strategy_state=None) -> ExecutionState:
    return ExecutionState(
        task_type="backtest",
        task_id=uuid4(),
        execution_id=uuid4(),
        current_balance=Decimal("100000"),
        ticks_processed=ticks_processed,
        strategy_state=strategy_state or {},
    )


def _tick(index: int, mid: str) -> Tick:
    value = Decimal(mid)
    return Tick(
        instrument="USD_JPY",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
        bid=value - Decimal("0.001"),
        ask=value + Decimal("0.001"),
        mid=value,
    )


def _apply_open(strategy: NetGridStrategy, state: ExecutionState, event: OpenPositionEvent) -> None:
    strategy.apply_event_execution_result(
        state=state,
        execution_result=EventExecutionResult(
            execution_price=event.price,
            executed_units=event.units,
            entry_binding=EntryExecutionBinding(
                entry_id=event.entry_id,
                position_id=str(uuid4()),
                fill_price=event.price,
            ),
        ),
    )


def test_initial_tick_opens_one_sided_net_position_and_records_ledger() -> None:
    strategy = NetGridStrategy("USD_JPY", Decimal("0.01"), NetGridConfig())
    state = _state()

    result = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    open_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert open_event.strategy_type == "net_grid"
    assert open_event.direction == "long"
    assert open_event.units == 1000

    _apply_open(strategy, result.state, open_event)
    strategy_state = result.state.strategy_state
    assert strategy_state["current_net_units"] == 1000
    assert strategy_state["average_entry_price"] == str(open_event.price)
    assert strategy_state["grid_ledger"][-1]["action"] == "open"
    assert strategy_state["grid_ledger"][-1]["source"] == "event_execution"


def test_adverse_grid_move_adds_to_existing_net_position() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(grid_interval_pips=Decimal("10"), cooldown_ticks=0),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "149.890"), state=first.state)
    add_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert add_event.units == 1000
    assert add_event.direction == "long"

    _apply_open(strategy, result.state, add_event)
    strategy_state = result.state.strategy_state
    assert strategy_state["current_net_units"] == 2000
    assert strategy_state["step"] == 1
    assert strategy_state["grid_ledger"][-1]["action"] == "add"


def test_average_price_take_profit_closes_net_position() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(take_profit_pips=Decimal("5"), cooldown_ticks=0),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "150.060"), state=first.state)
    close_event = next(event for event in result.events if isinstance(event, ClosePositionEvent))
    assert close_event.close_reason == "net_grid_take_profit"
    assert close_event.units == 1000

    strategy.apply_event_execution_result(
        state=result.state,
        execution_result=EventExecutionResult(
            realized_pnl_delta=Decimal("59"),
            realized_pnl_delta_quote=Decimal("59"),
            execution_price=close_event.exit_price,
            executed_units=close_event.units,
        ),
    )
    strategy_state = result.state.strategy_state
    assert strategy_state["current_net_units"] == 0
    assert strategy_state["average_entry_price"] is None
    assert strategy_state["grid_ledger"][-1]["action"] == "take_profit"
