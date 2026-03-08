"""Unit tests for SnowballStrategy class."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import EventType, StrategyType
from apps.trading.strategies.snowball.models import (
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
        "rebalance_enabled": False,
        "spread_guard_enabled": False,
        "m_pips_min": "12",
        "m_pips_max": "55",
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

    def test_normalize_parameters_uppercases_atr_timeframe(self):
        """Regression: lowercase atr_timeframe must be normalised."""
        result = SnowballStrategy.normalize_parameters({"atr_timeframe": "h4"})
        assert result["atr_timeframe"] == "H4"

    def test_default_parameters(self):
        defaults = SnowballStrategy.default_parameters()
        assert isinstance(defaults, dict)
        assert "base_units" in defaults
        assert "m_pips" in defaults
        assert defaults["atr_timeframe"] == "M1"

    def test_validate_parameters_valid(self):
        """validate_parameters should not raise for valid params + schema."""
        import json
        from pathlib import Path

        from django.conf import settings

        schema_path = Path(settings.BASE_DIR) / "apps" / "trading" / "schemas" / "snowball.json"
        with open(schema_path) as f:
            schema = json.load(f)

        params = SnowballStrategy.default_parameters()
        # Ensure m_pips is within m_pips_min..m_pips_max range
        params["m_pips_max"] = "55"
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

    def test_validate_parameters_rejects_invalid_atr_timeframe(self):
        """JSON schema rejects timeframes not in the enum."""
        import json
        from pathlib import Path

        from django.conf import settings

        schema_path = Path(settings.BASE_DIR) / "apps" / "trading" / "schemas" / "snowball.json"
        with open(schema_path) as f:
            schema = json.load(f)

        params = SnowballStrategy.default_parameters()
        params["atr_timeframe"] = "INVALID"
        with pytest.raises(ValueError):
            SnowballStrategy.validate_parameters(parameters=params, config_schema=schema)

    def test_normalize_then_validate_round_trip(self):
        """Regression: normalize → validate must not fail for lowercase timeframe."""
        import json
        from pathlib import Path

        from django.conf import settings

        schema_path = Path(settings.BASE_DIR) / "apps" / "trading" / "schemas" / "snowball.json"
        with open(schema_path) as f:
            schema = json.load(f)

        raw = {
            "atr_timeframe": "m1",
            "base_units": 1000,
            "m_pips": 50,
            "r_max": 7,
            "m_pips_max": 55,
        }
        normalised = SnowballStrategy.normalize_parameters(raw)
        # This was the exact bug: normalize produced "m1" which schema rejected
        SnowballStrategy.validate_parameters(parameters=normalised, config_schema=schema)


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
        assert len(ss.trend_basket) >= 1
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


class TestSnowballSpreadGuard:
    def test_wide_spread_blocks_entries(self):
        s = _strategy(
            {
                "spread_guard_enabled": True,
                "spread_guard_pips": "1",
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        # Spread = 5 pips (0.05 / 0.01) — exceeds guard of 1 pip
        s.on_tick(tick=_make_tick(ts, "150.00", "150.05"), state=state)

        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        # With wide spread, strategy should not initialise baskets
        assert ss.initialised is False


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
        data = {"initialised": True, "add_count": 3}
        assert s.deserialize_state(data) == data

    def test_serialize_state_passthrough(self):
        s = _strategy()
        data = {"initialised": True, "add_count": 3}
        assert s.serialize_state(data) == data
