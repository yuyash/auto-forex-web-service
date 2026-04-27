"""Unit tests for the Net Grid strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

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


def test_validate_parameters_rejects_invalid_ema_relationship() -> None:
    params = NetGridStrategy.normalize_parameters(
        {"direction_mode": "auto", "auto_fast_ema_ticks": 20, "auto_slow_ema_ticks": 5}
    )

    with pytest.raises(ValueError, match="auto_fast_ema_ticks"):
        NetGridStrategy.validate_parameters(parameters=params, config_schema=None)


def test_validate_parameters_rejects_invalid_adaptive_bounds() -> None:
    params = NetGridStrategy.normalize_parameters(
        {"grid_spacing_mode": "atr", "grid_min_interval_pips": 30, "grid_max_interval_pips": 10}
    )

    with pytest.raises(ValueError, match="grid_min_interval_pips"):
        NetGridStrategy.validate_parameters(parameters=params, config_schema=None)


def test_auto_direction_waits_for_trend_samples_before_initial_entry() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(direction_mode="auto"),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    assert not any(isinstance(event, OpenPositionEvent) for event in first.events)
    assert first.state.strategy_state["latest_decision"]["reason"] == "auto_direction_warming_up"

    first.state.ticks_processed = 1
    second = strategy.on_tick(tick=_tick(1, "150.005"), state=first.state)
    assert not any(isinstance(event, OpenPositionEvent) for event in second.events)
    assert second.state.strategy_state["latest_decision"]["reason"] == "auto_direction_warming_up"


def test_auto_direction_opens_long_when_recent_trend_is_up() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(direction_mode="auto"),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first.state.ticks_processed = 1
    second = strategy.on_tick(tick=_tick(1, "150.005"), state=first.state)
    second.state.ticks_processed = 2
    result = strategy.on_tick(tick=_tick(2, "150.020"), state=second.state)

    open_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert open_event.direction == "long"
    assert result.state.strategy_state["latest_decision"]["reason"] == "initial_entry_auto_trend"


def test_auto_direction_opens_short_when_recent_trend_is_down() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(direction_mode="auto"),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first.state.ticks_processed = 1
    second = strategy.on_tick(tick=_tick(1, "149.995"), state=first.state)
    second.state.ticks_processed = 2
    result = strategy.on_tick(tick=_tick(2, "149.980"), state=second.state)

    open_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert open_event.direction == "short"
    assert result.state.strategy_state["latest_decision"]["reason"] == "initial_entry_auto_trend"


def test_auto_direction_holds_when_recent_trend_is_flat() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(direction_mode="auto"),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first.state.ticks_processed = 1
    second = strategy.on_tick(tick=_tick(1, "150.004"), state=first.state)
    second.state.ticks_processed = 2
    result = strategy.on_tick(tick=_tick(2, "150.006"), state=second.state)

    assert not any(isinstance(event, OpenPositionEvent) for event in result.events)
    assert result.state.strategy_state["latest_decision"]["reason"] == "auto_direction_neutral"


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


def test_atr_grid_spacing_uses_recent_tick_volatility_for_add_distance() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            grid_spacing_mode="atr",
            grid_atr_multiplier=Decimal("2"),
            grid_min_interval_pips=Decimal("5"),
            grid_max_interval_pips=Decimal("50"),
            atr_period_ticks=3,
            cooldown_ticks=0,
        ),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    inside = strategy.on_tick(tick=_tick(1, "149.950"), state=first.state)
    assert not any(isinstance(event, OpenPositionEvent) for event in inside.events)
    assert inside.state.strategy_state["latest_decision"]["reason"] == "inside_grid"
    assert inside.state.strategy_state["effective_grid_interval_pips"] == "10.0"

    inside.state.ticks_processed = 2
    result = strategy.on_tick(tick=_tick(2, "149.890"), state=inside.state)
    add_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert add_event.direction == "long"
    assert result.state.strategy_state["effective_grid_interval_pips"] == "11.0"


def test_atr_take_profit_uses_recent_tick_volatility_for_exit_distance() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            take_profit_mode="atr",
            take_profit_atr_multiplier=Decimal("2"),
            take_profit_min_pips=Decimal("2"),
            take_profit_max_pips=Decimal("5"),
            cooldown_ticks=0,
        ),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "150.060"), state=first.state)
    close_event = next(event for event in result.events if isinstance(event, ClosePositionEvent))
    assert close_event.close_reason == "net_grid_take_profit"
    assert result.state.strategy_state["effective_take_profit_pips"] == "5"


def test_cooldown_seconds_blocks_order_even_when_tick_cooldown_allows() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            grid_interval_pips=Decimal("5"),
            cooldown_ticks=0,
            cooldown_seconds=10,
        ),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "149.900"), state=first.state)

    assert not any(isinstance(event, OpenPositionEvent) for event in result.events)
    assert result.state.strategy_state["latest_decision"]["reason"] == "cooldown_seconds"


def test_regime_filter_blocks_new_entry_during_high_volatility() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            direction_mode="auto",
            regime_filter_enabled=True,
            regime_max_atr_pips=Decimal("3"),
            cooldown_ticks=0,
        ),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "150.050"), state=first.state)

    assert not any(isinstance(event, OpenPositionEvent) for event in result.events)
    assert result.state.strategy_state["latest_decision"]["reason"] == "regime_high_volatility"
    assert result.state.strategy_state["regime_status"] == "blocked_high_volatility"


def test_regime_filter_blocks_counter_trend_add_step() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            grid_interval_pips=Decimal("5"),
            cooldown_ticks=0,
            regime_filter_enabled=True,
            regime_trend_guard_pips=Decimal("0.1"),
        ),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "149.900"), state=first.state)

    assert not any(isinstance(event, OpenPositionEvent) for event in result.events)
    assert result.state.strategy_state["latest_decision"]["reason"] == "regime_counter_trend"


def test_volatility_size_mode_reduces_add_units() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(
            grid_interval_pips=Decimal("5"),
            cooldown_ticks=0,
            volatility_size_mode="atr",
            volatility_size_atr_threshold_pips=Decimal("20"),
            volatility_size_min_multiplier=Decimal("0.5"),
        ),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    result = strategy.on_tick(tick=_tick(1, "149.500"), state=first.state)

    add_event = next(event for event in result.events if isinstance(event, OpenPositionEvent))
    assert add_event.units == 500
    assert result.state.strategy_state["effective_order_size_multiplier"] == "0.5"


def test_full_grid_hold_timeout_closes_net_position() -> None:
    strategy = NetGridStrategy(
        "USD_JPY",
        Decimal("0.01"),
        NetGridConfig(max_steps=0, cooldown_ticks=0, max_full_grid_ticks=2),
    )
    state = _state()
    first = strategy.on_tick(tick=_tick(0, "150.000"), state=state)
    first_open = next(event for event in first.events if isinstance(event, OpenPositionEvent))
    _apply_open(strategy, first.state, first_open)

    first.state.ticks_processed = 1
    hold = strategy.on_tick(tick=_tick(1, "149.990"), state=first.state)
    assert not any(isinstance(event, ClosePositionEvent) for event in hold.events)

    hold.state.ticks_processed = 2
    result = strategy.on_tick(tick=_tick(2, "149.990"), state=hold.state)

    close_event = next(event for event in result.events if isinstance(event, ClosePositionEvent))
    assert close_event.close_reason == "net_grid_risk_exit"
    assert result.state.strategy_state["latest_decision"]["reason"] == "max_full_grid_ticks"


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
