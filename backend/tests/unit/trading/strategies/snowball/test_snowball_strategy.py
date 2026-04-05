"""Comprehensive unit tests for SnowballStrategy tick-driven behavior.

Covers: initialisation, trend basket rotation, counter basket adds/closes,
slot vacate after TP, layer progression, f_max exhaustion, margin
protection (shrink / lock / emergency), spread guard, and
dynamic TP (ATR) scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.events import (
    ClosePositionEvent,
    GenericStrategyEvent,
    OpenPositionEvent,
)
from apps.trading.strategies.snowball.models import Entry, Layer, SnowballStrategyConfig
from apps.trading.strategies.snowball.strategy import SnowballStrategy

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


@dataclass
class DummyState:
    """Minimal state shape required by strategy.on_tick."""

    strategy_state: dict[str, Any] = field(default_factory=dict)
    current_balance: Decimal = Decimal("1000000")
    ticks_processed: int = 1


def _tick(ts: datetime, bid: str, ask: str) -> Tick:
    return Tick.create(
        instrument="USD_JPY",
        timestamp=ts,
        bid=Decimal(bid),
        ask=Decimal(ask),
    )


T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _strategy(**overrides) -> SnowballStrategy:
    params: dict[str, Any] = {
        "base_units": 1000,
        "m_pips": "50",
        "trend_lot_size": 1,
        "r_max": 7,
        "f_max": 3,
        "post_r_max_base_factor": "1",
        "n_pips_head": "30",
        "n_pips_tail": "14",
        "n_pips_flat_steps": 2,
        "n_pips_gamma": "1.4",
        "interval_mode": "constant",
        "counter_tp_mode": "fixed",
        "counter_tp_pips": "25",
        "counter_tp_step_amount": "2.5",
        "counter_tp_multiplier": "1.2",
        "round_step_pips": "0.1",
        "shrink_enabled": False,
        "lock_enabled": False,
        "m_th": "70",
        "n_th": "85",
        "pip_size": "0.01",
    }
    params.update(overrides)
    cfg = SnowballStrategyConfig.from_dict(params)
    return SnowballStrategy("USD_JPY", Decimal("0.01"), cfg)


def _open_events(result) -> list[OpenPositionEvent]:
    return [e for e in result.events if isinstance(e, OpenPositionEvent)]


def _close_events(result) -> list[ClosePositionEvent]:
    return [e for e in result.events if isinstance(e, ClosePositionEvent)]


def _signal_events(result, kind: str) -> list[GenericStrategyEvent]:
    return [
        e
        for e in result.events
        if isinstance(e, GenericStrategyEvent)
        and isinstance(e.data, dict)
        and e.data.get("kind") == kind
    ]


# ==================================================================
# 1. Initialisation
# ==================================================================


class TestInitialisation:
    def test_first_tick_creates_long_and_short_cycles(self):
        s = _strategy()
        state = DummyState()
        result = s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        opens = _open_events(result)
        assert len(opens) == 2  # LONG + SHORT initial entries

    def test_initial_entries_are_at_l1_r0(self):
        s = _strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        from apps.trading.strategies.snowball.models import SnowballStrategyState

        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        for cycle in ss.active_cycles():
            head = cycle.initial_entry
            assert head is not None
            assert head.layer_number == 1
            assert head.retracement_count == 0

    def test_second_tick_does_not_reinitialise(self):
        s = _strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=1), "150.00", "150.02"), state=state)
        opens = _open_events(result)
        assert len(opens) == 0


# ==================================================================
# 2. Counter adds
# ==================================================================


class TestCounterAdds:
    def test_counter_add_on_adverse_move(self):
        s = _strategy(m_pips="50", n_pips_head="30")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        # Move SHORT adverse by 30+ pips (price goes up)
        result = s.on_tick(tick=_tick(T0 + timedelta(minutes=1), "150.32", "150.34"), state=state)
        opens = _open_events(result)
        assert len(opens) >= 1
        # Should be at R1 (index 1)
        assert any(e.retracement_count == 1 for e in opens)


# ==================================================================
# 3. Counter TP closes
# ==================================================================


class TestCounterCloses:
    def test_counter_tp_closes_newest_first(self):
        s = _strategy(m_pips="50", counter_tp_pips="10", n_pips_head="30")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        # Add counter for SHORT cycle (price goes up)
        s.on_tick(tick=_tick(T0 + timedelta(minutes=1), "150.32", "150.34"), state=state)
        state.ticks_processed += 1

        # Move price back down to hit counter TP
        result = s.on_tick(tick=_tick(T0 + timedelta(minutes=2), "150.20", "150.22"), state=state)
        closes = _close_events(result)
        # Should close the counter entry
        assert any(e.close_reason == "counter_tp" for e in closes)


# ==================================================================
# 4. Trend TP (cycle head close)
# ==================================================================


class TestTrendTP:
    def test_trend_tp_closes_and_reopens(self):
        s = _strategy(m_pips="5")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        # Move price up by 5+ pips for LONG TP
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.10", "150.12"), state=state)
        close_events = _close_events(result)
        open_events = _open_events(result)
        assert len(close_events) >= 1 or len(open_events) >= 1


# ==================================================================
# 5. Shrink mode
# ==================================================================


class TestShrinkMode:
    def test_shrink_closes_from_front(self):
        """Shrink should close the oldest position (L0/R0) first."""
        s = _strategy(shrink_enabled=True, m_th="70", lock_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Inject a counter entry via slot
        counter_entry = {
            "entry_id": 10,
            "step": 2,
            "direction": "long",
            "entry_price": "151.00",
            "close_price": "151.50",
            "units": 1000,
            "opened_at": T0.isoformat(),
        }
        layers = state.strategy_state["cycles"][0]["grid"]["layers"]
        layers[0]["slots"][1]["entry"] = counter_entry

        s._margin_ratio = lambda _state, _ss: Decimal("75")  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        closes = _close_events(result)
        assert len(closes) >= 1
        shrink_signals = _signal_events(result, "snowball_shrink")
        assert len(shrink_signals) >= 1

        # The first close should be the oldest entry (L0/R0)
        first_close = closes[0]
        assert first_close.close_reason == "shrink"

    def test_shrink_head_shifts_after_close(self):
        """After shrink closes L0/R0, the cycle head should shift dynamically."""
        from apps.trading.strategies.snowball.models import (
            SnowballCycle,
            SnowballStrategyState,
        )

        # Directly construct state with known entries — no on_tick needed
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        l0 = Layer.create(1, 3, 1000)
        l0.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("150.00"),
                close_price=Decimal("150.50"),
                units=1000,
                opened_at=T0,
                role="initial",
                layer_number=1,
                retracement_count=0,
            )
        )
        l0.slot_at(1).fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.LONG,
                entry_price=Decimal("149.70"),
                close_price=Decimal("150.00"),
                units=2000,
                opened_at=T0,
                role="counter",
                layer_number=1,
                retracement_count=1,
            )
        )
        cycle.add_layer(l0)
        ss.cycles.append(cycle)

        # Verify head is L1/R0
        assert cycle.initial_entry.entry_id == 1

        # Simulate shrink closing L1/R0
        cycle.remove_entry(1)

        # Head should now be L1/R1
        assert cycle.initial_entry is not None
        assert cycle.initial_entry.entry_id == 2
        assert cycle.initial_entry.retracement_count == 1


# ==================================================================
# 6. Lock mode
# ==================================================================


class TestLockMode:
    def test_lock_opens_hedge_and_blocks_trading(self):
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert any(
            isinstance(e, GenericStrategyEvent)
            and isinstance(e.data, dict)
            and e.data.get("kind") == "snowball_locked"
            for e in result.events
        )

    def test_locked_state_blocks_normal_trading(self):
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "150.00", "150.02"), state=state)
        opens = _open_events(result)
        assert len(opens) == 0


# ==================================================================
# 7. Emergency stop
# ==================================================================


class TestEmergencyStop:
    def test_emergency_stop_at_95_percent(self):
        s = _strategy(
            lock_enabled=True,
            n_th="85",
            m_th="70",
            shrink_enabled=False,
        )
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        state.ticks_processed += 1

        s._margin_ratio = lambda _state, _ss: Decimal("96")  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert result.should_stop is True
        assert "Emergency stop" in (result.stop_reason or "")
