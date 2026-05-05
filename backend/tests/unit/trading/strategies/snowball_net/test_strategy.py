"""Unit tests for SnowballNet strategy behavior."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.trading.dataclasses import EntryExecutionBinding, EventExecutionResult, Tick
from apps.trading.enums import Direction, EventType
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


def _report():
    return SimpleNamespace(blockers=[], warnings=[])


def _position(
    *,
    id: str,
    direction: Direction = Direction.LONG,
    units: int = 1000,
    entry_price: str = "150.00",
):
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return SimpleNamespace(
        id=id,
        direction=direction,
        units=units,
        entry_price=Decimal(entry_price),
        entry_time=timestamp,
        created_at=timestamp,
    )


def test_snowball_net_registers_with_net_visualization_capability():
    assert registry.is_registered("snowball_net")
    capabilities = registry.capabilities(identifier="snowball_net")
    assert capabilities["runtime"]["hedging"] is False
    assert capabilities["runtime"]["netting"] is True
    assert capabilities["visualization"]["kind"] == "snowball_net"
    assert capabilities["resume"]["stateful_broker_reconciliation"] is True


def test_capacity_limit_mode_defaults_to_add_count_capacity():
    config = SnowballNetConfig.from_dict({})

    assert config.capacity_limit_mode == "add_count"
    assert config.max_net_units == 0
    assert config.effective_max_net_units == 8000
    assert config.add_unit_allocation_mode == "fixed"


def test_legacy_max_net_units_implies_explicit_capacity_limit_mode():
    config = SnowballNetConfig.from_dict({"max_net_units": 5000})

    assert config.capacity_limit_mode == "max_net_units"
    assert config.max_net_units == 5000
    assert config.effective_max_net_units == 5000


def test_add_count_capacity_ignores_stale_net_unit_limit_settings():
    config = SnowballNetConfig.from_dict(
        {
            "capacity_limit_mode": "add_count",
            "max_net_units": 5000,
            "add_unit_allocation_mode": "remaining_linear",
        }
    )

    assert config.max_net_units == 0
    assert config.add_unit_allocation_mode == "fixed"
    assert config.effective_max_net_units == 8000


def test_max_net_unit_capacity_requires_positive_max_net_units():
    config = SnowballNetConfig.from_dict(
        {
            "capacity_limit_mode": "max_net_units",
            "max_net_units": 0,
        }
    )

    with pytest.raises(ValueError, match="max_net_units must be set"):
        config.validate()


@pytest.mark.parametrize("mode", ["additive", "multiplicative"])
def test_increasing_interval_modes_require_tail_at_least_head(mode):
    config = SnowballNetConfig.from_dict(
        {
            "interval_mode": mode,
            "n_pips_head": 30,
            "n_pips_tail": 14,
        }
    )

    with pytest.raises(ValueError, match="greater than or equal to n_pips_head"):
        config.validate()


@pytest.mark.parametrize("mode", ["subtractive", "divisive"])
def test_decreasing_interval_modes_require_tail_at_most_head(mode):
    config = SnowballNetConfig.from_dict(
        {
            "interval_mode": mode,
            "n_pips_head": 30,
            "n_pips_tail": 45,
        }
    )

    with pytest.raises(ValueError, match="less than or equal to n_pips_head"):
        config.validate()


def test_increasing_interval_mode_progresses_toward_larger_tail():
    config = SnowballNetConfig.from_dict(
        {
            "interval_mode": "additive",
            "n_pips_head": 10,
            "n_pips_tail": 30,
            "n_pips_flat_steps": 0,
            "n_pips_gamma": 1,
            "max_add_count": 4,
        }
    )

    config.validate()

    assert config.add_interval_pips(1) == Decimal("15.0")
    assert config.add_interval_pips(4) == Decimal("30.0")


def test_reconcile_broker_positions_rebuilds_net_state_from_existing_positions():
    state = _state({})
    report = _report()
    strategy_config = SimpleNamespace(
        config_dict=SnowballNetConfig.from_dict({}).to_dict(),
    )

    SnowballNetStrategy.reconcile_broker_positions(
        state=state,
        open_positions=[
            _position(id="position-1", units=1000, entry_price="150.00"),
            _position(id="position-2", units=2000, entry_price="150.03"),
        ],
        report=report,
        strategy_config=strategy_config,
    )

    assert report.blockers == []
    assert state.strategy_state["initialised"] is True
    assert state.strategy_state["direction"] == "long"
    assert state.strategy_state["net_units"] == 3000
    assert Decimal(state.strategy_state["average_price"]) == Decimal("150.02")
    assert state.strategy_state["position_id"] == "position-1"
    assert state.strategy_state["add_count"] == 2


def test_reconcile_broker_positions_blocks_fixed_direction_mismatch():
    state = _state({})
    report = _report()
    strategy_config = SimpleNamespace(
        config_dict=SnowballNetConfig.from_dict({"trade_direction": "long"}).to_dict(),
    )

    SnowballNetStrategy.reconcile_broker_positions(
        state=state,
        open_positions=[
            _position(
                id="position-1",
                direction=Direction.SHORT,
                units=-1000,
                entry_price="150.00",
            )
        ],
        report=report,
        strategy_config=strategy_config,
    )

    assert report.blockers
    assert "does not match configured direction" in report.blockers[0]


def test_reconcile_broker_positions_clears_reflected_pending_open():
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 1000,
            "average_price": "150.00",
            "position_id": "position-1",
            "next_entry_id": 3,
            "pending_action": {
                "kind": "open",
                "entry_id": 2,
                "units": 1000,
                "previous_units": 1000,
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        }
    )
    report = _report()
    strategy_config = SimpleNamespace(config_dict=SnowballNetConfig.from_dict({}).to_dict())

    SnowballNetStrategy.reconcile_broker_positions(
        state=state,
        open_positions=[
            _position(id="position-1", units=2000, entry_price="149.99"),
        ],
        report=report,
        strategy_config=strategy_config,
    )

    assert state.strategy_state["pending_action"] == {}
    assert state.strategy_state["last_action"]["kind"] == "reconciled"
    assert state.strategy_state["last_action"]["action"] == "open"
    assert report.warnings


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


def test_loss_cut_defaults_to_disabled_with_100_pip_threshold():
    config = SnowballNetConfig.from_dict({})

    assert config.loss_cut_enabled is False
    assert config.loss_cut_threshold_pips == Decimal("100")


def test_auto_direction_waits_for_warmup_then_opens_with_ema_trend():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "trade_direction": "auto",
                "auto_direction_fast_period": 2,
                "auto_direction_slow_period": 3,
                "auto_direction_min_samples": 3,
            }
        ),
    )
    state = _state()

    first = strategy.on_tick(tick=_tick("149.99", "150.01"), state=state)
    assert first.events == []
    assert first.state.strategy_state["direction"] == "auto"
    assert first.state.strategy_state["last_action"]["action"] == "auto_direction_warmup"

    second = strategy.on_tick(tick=_tick("150.09", "150.11"), state=first.state)
    assert second.events == []

    third = strategy.on_tick(tick=_tick("150.19", "150.21"), state=second.state)
    assert len(third.events) == 1
    event = third.events[0]
    assert event.event_type == EventType.OPEN_POSITION
    assert event.direction == "long"
    assert third.state.strategy_state["direction"] == "long"
    assert third.state.strategy_state["auto_direction_last_decision"]["direction"] == "long"


def test_auto_direction_reselects_when_flat_again():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "trade_direction": "auto",
                "auto_direction_fast_period": 2,
                "auto_direction_slow_period": 3,
                "auto_direction_min_samples": 3,
            }
        ),
    )
    state = _state(
        {
            "initialised": False,
            "direction": "auto",
            "direction_mode": "auto",
            "net_units": 0,
            "auto_direction_samples": 3,
            "auto_direction_fast_ema": "149.90",
            "auto_direction_slow_ema": "150.00",
            "auto_direction_signal": "short",
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.79", "149.81"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.OPEN_POSITION
    assert event.direction == "short"
    assert result.state.strategy_state["direction"] == "short"


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


def test_margin_reduce_defaults_to_disabled():
    config = SnowballNetConfig.from_dict({})

    assert config.margin_reduce_enabled is False
    assert config.margin_reduce_threshold_pct == Decimal("70")
    assert config.margin_reduce_target_pct == Decimal("50")


def test_margin_reduce_closes_units_to_approach_target_when_enabled():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "margin_reduce_enabled": True,
                "margin_reduce_threshold_pct": 70,
                "margin_reduce_target_pct": 50,
                "max_add_count": 5,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 4000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 3,
            "next_entry_id": 5,
            "metrics": {"margin_ratio": "0.80"},
        }
    )

    result = strategy.on_tick(tick=_tick("150.00", "150.02"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.CLOSE_POSITION
    assert event.strategy_event_type == "snowball_net_margin_reduce"
    assert event.close_reason == "margin_protection"
    assert event.units == 1500
    assert result.state.strategy_state["pending_action"]["reason"] == "margin_reduce"


def test_emergency_stop_uses_configured_margin_threshold():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "emergency_enabled": True,
                "emergency_threshold_pct": 95,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 2000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 1,
            "metrics": {"margin_ratio": "0.96"},
        }
    )

    result = strategy.on_tick(tick=_tick("150.00", "150.02"), state=state)

    assert result.events == []
    assert result.should_stop is True
    assert result.stop_reason == "SnowballNet emergency margin threshold reached: 96.00%"


def test_loss_cut_emits_full_close_when_enabled():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "loss_cut_enabled": True,
                "loss_cut_threshold_pips": 10,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 3000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 2,
            "next_entry_id": 4,
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.89", "149.91"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == EventType.CLOSE_POSITION
    assert event.strategy_event_type == "snowball_net_loss_cut"
    assert event.close_reason == "net_loss_cut"
    assert event.units == 3000
    assert result.state.strategy_state["pending_action"]["reason"] == "loss_cut"


def test_loss_cut_close_execution_resets_net_state_for_restart():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "loss_cut_enabled": True,
                "loss_cut_threshold_pips": 10,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 3000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 2,
            "next_entry_id": 4,
            "metrics": {"margin_ratio": "0.10"},
        }
    )
    result = strategy.on_tick(tick=_tick("149.89", "149.91"), state=state)

    strategy.apply_event_execution_result(
        state=result.state,
        execution_result=EventExecutionResult(
            execution_price=Decimal("149.89"),
            executed_units=3000,
        ),
    )

    assert result.state.strategy_state["initialised"] is False
    assert result.state.strategy_state["net_units"] == 0
    assert result.state.strategy_state["average_price"] is None
    assert result.state.strategy_state["add_count"] == 0


def test_metrics_include_dotted_next_add_when_add_limit_reached():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict({"max_add_count": 1}),
    )
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

    result = strategy.on_tick(tick=_tick("149.68", "149.70"), state=state)
    metrics = result.state.strategy_state["metrics"]

    assert result.events == []
    assert metrics["snowball_net_can_add"] is False
    assert metrics["snowball_net_next_add_price"] is None
    assert metrics["snowball_net_theoretical_next_add_price"] == "149.700"


def test_add_trend_guard_blocks_add_when_long_far_below_trend_ema():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "add_trend_guard_enabled": True,
                "add_trend_max_opposite_deviation_pips": 50,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 1000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 0,
            "risk_trend_ema": "150.50",
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.68", "149.70"), state=state)

    assert result.events == []
    metrics = result.state.strategy_state["metrics"]
    assert metrics["snowball_net_can_add"] is False
    assert metrics["snowball_net_add_block_reason"] == "trend_deviation"


def test_adaptive_interval_widens_add_distance_when_volatility_is_high():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "adaptive_interval_enabled": True,
                "adaptive_interval_reference_pips": 10,
                "adaptive_interval_min_multiplier": "0.5",
                "adaptive_interval_max_multiplier": "3",
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 1000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 0,
            "metrics": {"margin_ratio": "0.10", "current_atr": "20"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.68", "149.70"), state=state)

    assert result.events == []
    interval = Decimal(
        result.state.strategy_state["metrics"]["snowball_net_effective_add_interval_pips"]
    )
    assert interval == Decimal("60.0")


def test_remaining_linear_add_allocation_uses_remaining_capacity():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "add_unit_allocation_mode": "remaining_linear",
                "max_net_units": 5000,
                "max_add_count": 4,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 3000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 1,
            "next_entry_id": 3,
            "metrics": {"margin_ratio": "0.10"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.68", "149.70"), state=state)

    assert len(result.events) == 1
    assert result.events[0].strategy_event_type == "snowball_net_add"
    assert result.events[0].units == 666


def test_staged_margin_loss_cut_closes_partial_units_instead_of_full_net():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "loss_cut_enabled": True,
                "loss_cut_mode": "staged_margin",
                "loss_cut_threshold_pips": 10,
                "loss_cut_stage_threshold_pct": 80,
                "loss_cut_stage_target_pct": 60,
            }
        ),
    )
    state = _state(
        {
            "initialised": True,
            "direction": "long",
            "net_units": 4000,
            "average_price": "150.00",
            "position_id": "position-1",
            "add_count": 3,
            "metrics": {"margin_ratio": "0.80"},
        }
    )

    result = strategy.on_tick(tick=_tick("149.89", "149.91"), state=state)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.strategy_event_type == "snowball_net_loss_cut"
    assert event.units == 1000


def test_auto_direction_filter_blocks_start_when_spread_is_wide():
    strategy = SnowballNetStrategy(
        "USD_JPY",
        Decimal("0.01"),
        SnowballNetConfig.from_dict(
            {
                "trade_direction": "auto",
                "auto_direction_fast_period": 2,
                "auto_direction_slow_period": 3,
                "auto_direction_min_samples": 3,
                "auto_direction_filter_enabled": True,
                "auto_direction_max_spread_pips": 1,
            }
        ),
    )
    state = _state(
        {
            "initialised": False,
            "direction": "auto",
            "direction_mode": "auto",
            "net_units": 0,
            "auto_direction_samples": 3,
            "auto_direction_fast_ema": "150.10",
            "auto_direction_slow_ema": "150.00",
            "auto_direction_signal": "long",
            "metrics": {"margin_ratio": "0.10", "current_atr": "1"},
        }
    )

    result = strategy.on_tick(tick=_tick("150.00", "150.03"), state=state)

    assert result.events == []
    assert result.state.strategy_state["last_action"]["action"] == "auto_direction_filtered"
    assert result.state.strategy_state["last_action"]["reason"] == "spread"
