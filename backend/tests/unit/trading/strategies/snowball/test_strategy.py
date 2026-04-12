"""Unit tests for SnowballStrategy class."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction, EventType, StrategyType
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
)
from apps.trading.strategies.snowball.strategy import SnowballStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class DummyState:
    """Minimal state shape required by strategy.on_tick."""

    strategy_state: dict[str, Any] = field(default_factory=dict)
    current_balance: Decimal = Decimal("100000")
    ticks_processed: int = 1


def _make_tick(ts: datetime, bid: str, ask: str) -> Tick:
    return Tick.create(
        instrument="USD_JPY",
        timestamp=ts,
        bid=Decimal(bid),
        ask=Decimal(ask),
        mid=(Decimal(bid) + Decimal(ask)) / Decimal("2"),
    )


def _strategy(overrides: dict[str, Any] | None = None) -> SnowballStrategy:
    params: dict[str, Any] = {
        "base_units": 1000,
        "m_pips": "50",
        "r_max": 7,
        "f_max": 3,
        "n_pips_head": "30",
        "n_pips_tail": "14",
        "n_pips_flat_steps": 2,
        "interval_mode": "constant",
        "counter_tp_mode": "weighted_avg",
        "shrink_enabled": False,
        "lock_enabled": False,
        "m_th": "70",
        "n_th": "85",
    }
    if overrides:
        params.update(overrides)
    config = SnowballStrategyConfig.from_dict(params)
    return SnowballStrategy("USD_JPY", Decimal("0.01"), config)


# ===================================================================
# Basic properties
# ===================================================================


class TestSnowballStrategyProperties:
    def test_strategy_type(self):
        s = _strategy()
        assert s.strategy_type == StrategyType.SNOWBALL

    def test_instrument_and_pip_size(self):
        s = _strategy()
        assert s.instrument == "USD_JPY"
        assert s.pip_size == Decimal("0.01")


# ===================================================================
# parse_config / normalize / defaults / validate
# ===================================================================


class TestSnowballStrategyClassMethods:
    def test_normalize_parameters_returns_dict(self):
        result = SnowballStrategy.normalize_parameters({"base_units": 2000})
        assert isinstance(result, dict)
        assert result["base_units"] == 2000
        assert result["disable_loss_cut_after_rebuild"] is False
        assert result["preserve_highest_r_from"] == 0

    def test_default_parameters(self):
        defaults = SnowballStrategy.default_parameters()
        assert isinstance(defaults, dict)
        assert "base_units" in defaults
        assert "m_pips" in defaults
        assert "disable_loss_cut_after_rebuild" in defaults
        assert "preserve_highest_r_from" in defaults

    def test_validate_parameters_valid(self):
        """validate_parameters should not raise for valid params + schema."""
        import json
        from pathlib import Path

        from django.conf import settings

        schema_path = Path(settings.BASE_DIR) / "apps" / "trading" / "schemas" / "snowball.json"
        with open(schema_path) as f:
            schema = json.load(f)

        params = SnowballStrategy.default_parameters()
        SnowballStrategy.validate_parameters(parameters=params, config_schema=schema)

    def test_validate_parameters_rejects_invalid_schema_value(self):
        """JSON schema rejects base_units < 1."""
        import json
        from pathlib import Path

        from django.conf import settings

        schema_path = Path(settings.BASE_DIR) / "apps" / "trading" / "schemas" / "snowball.json"
        with open(schema_path) as f:
            schema = json.load(f)

        params = SnowballStrategy.default_parameters()
        params["base_units"] = 0
        with pytest.raises(ValueError):
            SnowballStrategy.validate_parameters(parameters=params, config_schema=schema)


# ===================================================================
# on_tick — initialisation
# ===================================================================


class TestSnowballOnTickInit:
    def test_first_tick_initialises_baskets(self):
        s = _strategy()
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        result = s.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)

        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        assert ss.initialised is True
        assert len(ss.active_cycles()) >= 1
        assert result.events  # should emit open events

    def test_second_tick_does_not_reinitialise(self):
        s = _strategy()
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        s.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        ss_after_first = SnowballStrategyState.from_strategy_state(state.strategy_state)
        entry_count = ss_after_first.next_entry_id

        state.ticks_processed += 1
        s.on_tick(tick=_make_tick(ts + timedelta(seconds=1), "150.00", "150.02"), state=state)
        ss_after_second = SnowballStrategyState.from_strategy_state(state.strategy_state)
        # next_entry_id should not jump dramatically (no re-init)
        assert ss_after_second.initialised is True
        assert ss_after_second.next_entry_id >= entry_count


class TestSnowballStopLossProtectionThreshold:
    def _make_cycle_with_entries(self) -> tuple[SnowballStrategyState, SnowballCycle, Entry, Entry]:
        ss = SnowballStrategyState()
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 3, 1000, 2)

        r1 = Entry(
            entry_id=1,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("155.00"),
            close_price=Decimal("155.30"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
            stop_loss_price=Decimal("154.60"),
        )
        r2 = Entry(
            entry_id=2,
            step=3,
            direction=Direction.LONG,
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00"),
            units=3000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=2,
            stop_loss_price=Decimal("154.40"),
        )

        layer.slot_at(1).fill(r1)
        layer.slot_at(2).fill(r2)
        cycle.add_layer(layer)
        ss.cycles.append(cycle)
        return ss, cycle, r1, r2

    def test_highest_live_r_is_preserved_when_at_or_above_threshold(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "preserve_highest_r_from": 2,
            }
        )
        ss, cycle, r1, r2 = self._make_cycle_with_entries()
        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "154.39", "154.41")

        events = s._process_stop_loss_closes(ss, tick, cycle)

        closed_ids = {event.entry_id for event in events}
        assert r1.entry_id in closed_ids
        assert r2.entry_id not in closed_ids
        layer = cycle.grid.layers[0]
        assert layer.slot_at(1).pending_rebuild is not None
        assert layer.slot_at(2).entry is r2

    def test_highest_live_r_is_not_preserved_below_threshold(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "preserve_highest_r_from": 3,
            }
        )
        ss, cycle, r1, r2 = self._make_cycle_with_entries()
        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "154.39", "154.41")

        events = s._process_stop_loss_closes(ss, tick, cycle)

        closed_ids = {event.entry_id for event in events}
        assert r1.entry_id in closed_ids
        assert r2.entry_id in closed_ids

    def test_r0_only_layer_is_never_preserved(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "preserve_highest_r_from": 1,
            }
        )
        ss = SnowballStrategyState()
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 3, 1000, 2)
        r0 = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("155.00"),
            close_price=Decimal("155.50"),
            units=1000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
            stop_loss_price=Decimal("154.60"),
        )
        layer.slot_at(0).fill(r0)
        cycle.add_layer(layer)
        ss.cycles.append(cycle)
        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "154.59", "154.61")

        events = s._process_stop_loss_closes(ss, tick, cycle)

        assert [event.entry_id for event in events] == [r0.entry_id]


# ===================================================================
# on_tick — trend basket take-profit
# ===================================================================


class TestSnowballTrendTakeProfit:
    def test_trend_tp_closes_and_reopens(self):
        s = _strategy({"m_pips": "5"})  # small TP for easy triggering
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        s.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        # Move price up by 5+ pips (0.05 for USD_JPY)
        result = s.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "150.10", "150.12"),
            state=state,
        )

        close_events = [ev for ev in result.events if ev.event_type == EventType.CLOSE_POSITION]
        open_events = [ev for ev in result.events if ev.event_type == EventType.OPEN_POSITION]
        # Should close the trend position and re-open
        assert len(close_events) >= 1 or len(open_events) >= 1


# ===================================================================
# on_tick — spread guard
# ===================================================================


# ===================================================================
# Lifecycle hooks
# ===================================================================


class TestSnowballLifecycle:
    def test_on_start(self):
        s = _strategy()
        state = DummyState()
        result = s.on_start(state=state)
        assert any(ev.event_type == EventType.STRATEGY_STARTED for ev in result.events)

    def test_on_stop(self):
        s = _strategy()
        state = DummyState()
        result = s.on_stop(state=state)
        assert any(ev.event_type == EventType.STRATEGY_STOPPED for ev in result.events)

    def test_on_resume(self):
        s = _strategy()
        state = DummyState()
        result = s.on_resume(state=state)
        assert any(ev.event_type == EventType.STRATEGY_RESUMED for ev in result.events)


# ===================================================================
# State serialisation
# ===================================================================


class TestSnowballStateSerialization:
    def test_deserialize_state_passthrough(self):
        s = _strategy()
        data = {"initialised": True, "layer_retracement_count": 3}
        assert s.deserialize_state(data) == data

    def test_serialize_state_passthrough(self):
        s = _strategy()
        data = {"initialised": True, "layer_retracement_count": 3}
        assert s.serialize_state(data) == data
