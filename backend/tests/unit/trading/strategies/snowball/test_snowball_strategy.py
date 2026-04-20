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
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
)
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


def test_next_available_counter_slot_blocks_refill_below_higher_present_slot():
    layer = Layer.create(3, 7, 1000, 5)
    layer.slot_at(0).fill(
        Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("157.727"),
            close_price=Decimal("158.193"),
            units=1000,
            opened_at=T0,
            role="layer_initial",
            layer_number=3,
            retracement_count=0,
            root_entry_id=1,
        )
    )
    layer.slot_at(1).fill(
        Entry(
            entry_id=2,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("157.427"),
            close_price=Decimal("157.738"),
            units=2000,
            opened_at=T0,
            role="counter",
            layer_number=3,
            retracement_count=1,
            root_entry_id=1,
            parent_entry_id=1,
        )
    )
    layer.slot_at(2).fill(
        Entry(
            entry_id=3,
            step=3,
            direction=Direction.LONG,
            entry_price=Decimal("157.118"),
            close_price=Decimal("157.377"),
            units=3000,
            opened_at=T0,
            role="counter",
            layer_number=3,
            retracement_count=2,
            root_entry_id=1,
            parent_entry_id=1,
        )
    )
    layer.slot_at(4).fill(
        Entry(
            entry_id=4,
            step=5,
            direction=Direction.LONG,
            entry_price=Decimal("155.380"),
            close_price=Decimal("156.157"),
            units=5000,
            opened_at=T0,
            role="counter",
            layer_number=3,
            retracement_count=4,
            root_entry_id=1,
            parent_entry_id=1,
        )
    )

    assert layer.next_available_counter_slot() is None
    assert layer.needs_new_layer is True


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

    def test_weighted_avg_counter_add_does_not_double_count_live_r0(self):
        s = _strategy(counter_tp_mode="weighted_avg", interval_mode="constant", n_pips_head="30")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)

        layer1 = Layer.create(1, 7, 1000, 3)
        layer1.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("161.787"),
                close_price=Decimal("162.287"),
                units=1000,
                opened_at=T0,
                role="initial",
                layer_number=1,
                retracement_count=0,
                root_entry_id=1,
            )
        )

        layer3 = Layer.create(3, 7, 1000, 3)
        layer3.slot_at(0).fill(
            Entry(
                entry_id=2,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("157.497"),
                close_price=Decimal("158.0395"),
                units=1000,
                opened_at=T0,
                role="layer_initial",
                layer_number=3,
                retracement_count=0,
                root_entry_id=1,
                parent_entry_id=1,
            )
        )

        cycle.add_layer(layer1)
        cycle.add_layer(layer3)
        ss.cycles.append(cycle)

        tick = _tick(T0 + timedelta(minutes=1), "157.174", "157.194")
        events = s._process_cycle_counter_adds(ss, tick, cycle)

        assert len(events) == 1
        event = events[0]
        assert event.retracement_count == 1
        assert event.planned_exit_price_formula == "(157.194 * 2000 + 157.497 * 1000) / 3000"
        assert event.planned_exit_price == Decimal("157.295")

    def test_initial_r0_stop_loss_matches_r1_interval_distance(self):
        s = _strategy(m_pips="50", n_pips_head="30", stop_loss_enabled=True)
        state = DummyState()

        result = s.on_tick(tick=_tick(T0, "100.00", "100.00"), state=state)

        initial_open = _open_events(result)[0]
        assert initial_open.retracement_count == 0
        assert initial_open.stop_loss_price == Decimal("99.70")

    def test_refill_counter_is_blocked_when_higher_slot_is_still_present(self):
        s = _strategy(counter_tp_mode="fixed", counter_tp_pips="25", n_pips_head="30")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)

        layer = Layer.create(3, 7, 1000, 3)
        r0 = layer.slot_at(0)
        assert r0 is not None
        r0.fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("157.230"),
                close_price=Decimal("157.950"),
                units=1000,
                opened_at=T0,
                role="layer_initial",
                layer_number=3,
                retracement_count=0,
                root_entry_id=1,
            )
        )
        r3 = layer.slot_at(3)
        assert r3 is not None
        r3.fill(
            Entry(
                entry_id=2,
                step=4,
                direction=Direction.LONG,
                entry_price=Decimal("156.000"),
                close_price=Decimal("156.250"),
                units=4000,
                opened_at=T0,
                role="counter",
                layer_number=3,
                retracement_count=3,
                root_entry_id=1,
                parent_entry_id=1,
            )
        )

        cycle.add_layer(layer)
        ss.cycles.append(cycle)

        tick = _tick(T0 + timedelta(minutes=1), "156.90", "156.92")
        events = s._process_cycle_counter_adds(ss, tick, cycle)

        assert events == []

    def test_counter_add_uses_entry_side_price_not_mid(self):
        s = _strategy(counter_tp_mode="weighted_avg", interval_mode="constant", n_pips_head="30")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)

        layer = Layer.create(3, 7, 1000, 3)
        slot0 = layer.slot_at(0)
        assert slot0 is not None
        slot0.fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("157.230"),
                close_price=Decimal("157.95129"),
                units=1000,
                opened_at=T0,
                role="layer_initial",
                layer_number=3,
                retracement_count=0,
                root_entry_id=1,
            )
        )

        cycle.add_layer(layer)
        ss.cycles.append(cycle)

        bad_tick = Tick(
            instrument="USD_JPY",
            timestamp=T0 + timedelta(minutes=1),
            bid=Decimal("146.202"),
            ask=Decimal("163.225"),
            mid=Decimal("154.7135"),
        )

        events = s._process_cycle_counter_adds(ss, bad_tick, cycle)

        assert events == []


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

    def test_non_primary_layer_r0_close_removes_empty_layer(self):
        from apps.trading.strategies.snowball.models import (
            SnowballCycle,
            SnowballStrategyState,
        )

        s = _strategy(counter_tp_mode="fixed", counter_tp_pips="25")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.SHORT)

        layer2 = Layer.create(2, 7, 1000)
        layer2.slot_at(5).fill(
            Entry(
                entry_id=25,
                step=6,
                direction=Direction.SHORT,
                entry_price=Decimal("143.203"),
                close_price=Decimal("142.667"),
                units=6000,
                opened_at=T0,
                role="counter",
                layer_number=2,
                retracement_count=5,
            )
        )
        layer2.slot_at(6).fill(
            Entry(
                entry_id=26,
                step=7,
                direction=Direction.SHORT,
                entry_price=Decimal("143.342"),
                close_price=Decimal("142.815"),
                units=7000,
                opened_at=T0,
                role="counter",
                layer_number=2,
                retracement_count=6,
            )
        )
        layer2.slot_at(7).fill(
            Entry(
                entry_id=27,
                step=8,
                direction=Direction.SHORT,
                entry_price=Decimal("143.471"),
                close_price=Decimal("142.946"),
                units=8000,
                opened_at=T0,
                role="counter",
                layer_number=2,
                retracement_count=7,
            )
        )

        layer3 = Layer.create(3, 7, 1000)
        layer3.slot_at(0).fill(
            Entry(
                entry_id=30,
                step=1,
                direction=Direction.SHORT,
                entry_price=Decimal("143.587"),
                close_price=Decimal("142.946"),
                units=1000,
                opened_at=T0,
                role="layer_initial",
                layer_number=3,
                retracement_count=0,
            )
        )

        cycle.add_layer(layer2)
        cycle.add_layer(layer3)
        ss.cycles.append(cycle)
        state = DummyState(strategy_state=ss.to_dict())

        result = s.on_tick(tick=_tick(T0 + timedelta(minutes=1), "142.918", "142.938"), state=state)

        closes = _close_events(result)
        assert any(e.layer_number == 3 and e.retracement_count == 0 for e in closes)

        from apps.trading.strategies.snowball.models import SnowballStrategyState

        updated = SnowballStrategyState.from_strategy_state(state.strategy_state)
        updated_cycle = updated.cycles[0]
        assert [layer.layer_number for layer in updated_cycle.grid.layers] == [2]


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

    def test_shrink_preserves_existing_counter_tp(self):
        """Shrink must not rewrite surviving counter TPs."""
        s = _strategy(shrink_enabled=True, m_th="70", lock_enabled=False)
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.SHORT)
        layer = Layer.create(1, 7, 1000)
        layer.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.SHORT,
                entry_price=Decimal("142.000"),
                close_price=Decimal("141.850"),
                units=1000,
                opened_at=T0,
                role="initial",
                layer_number=1,
                retracement_count=0,
            )
        )
        layer.slot_at(1).fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.SHORT,
                entry_price=Decimal("142.300"),
                close_price=Decimal("142.120"),
                units=2000,
                opened_at=T0,
                role="counter",
                layer_number=1,
                retracement_count=1,
            )
        )
        cycle.add_layer(layer)
        ss.cycles.append(cycle)

        state = DummyState(strategy_state=ss.to_dict(), current_balance=Decimal("100"))
        s._margin_ratio = lambda _state, _ss: Decimal("75")  # type: ignore[method-assign]

        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "145.00", "145.02"), state=state)

        closes = _close_events(result)
        assert len(closes) == 1
        assert closes[0].close_reason == "shrink"
        assert closes[0].entry_id == 1

        persisted = SnowballStrategyState.from_strategy_state(state.strategy_state)
        remaining = persisted.cycles[0].grid.layers[0].slot_at(1).entry
        assert remaining is not None
        assert remaining.entry_id == 2
        assert remaining.close_price == Decimal("142.120")


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


class TestGridOrderingValidation:
    def test_long_cycle_fails_when_entry_prices_are_not_descending(self):
        s = _strategy(counter_tp_mode="fixed", counter_tp_pips="25")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 7, 1000, 3)
        layer.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("160.000"),
                close_price=Decimal("160.500"),
                units=1000,
                opened_at=T0,
                role="initial",
                layer_number=1,
                retracement_count=0,
                root_entry_id=1,
            )
        )
        layer.slot_at(1).fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.LONG,
                entry_price=Decimal("160.100"),
                close_price=Decimal("160.400"),
                units=2000,
                opened_at=T0,
                role="counter",
                layer_number=1,
                retracement_count=1,
                root_entry_id=1,
                parent_entry_id=1,
            )
        )
        cycle.add_layer(layer)
        ss.cycles.append(cycle)

        state = DummyState(strategy_state=ss.to_dict())
        result = s.on_tick(tick=_tick(T0 + timedelta(minutes=1), "160.10", "160.12"), state=state)

        assert result.should_stop is True
        assert result.is_error is True
        assert "Grid ordering violation" in (result.stop_reason or "")

    def test_short_cycle_fails_when_tp_prices_are_not_ascending(self):
        s = _strategy(counter_tp_mode="fixed", counter_tp_pips="25")
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=2, direction=Direction.SHORT)
        layer = Layer.create(1, 7, 1000, 3)
        layer.slot_at(0).fill(
            Entry(
                entry_id=10,
                step=1,
                direction=Direction.SHORT,
                entry_price=Decimal("150.000"),
                close_price=Decimal("149.500"),
                units=1000,
                opened_at=T0,
                role="initial",
                layer_number=1,
                retracement_count=0,
                root_entry_id=10,
            )
        )
        layer.slot_at(1).fill(
            Entry(
                entry_id=11,
                step=2,
                direction=Direction.SHORT,
                entry_price=Decimal("150.300"),
                close_price=Decimal("149.400"),
                units=2000,
                opened_at=T0,
                role="counter",
                layer_number=1,
                retracement_count=1,
                root_entry_id=10,
                parent_entry_id=10,
            )
        )
        cycle.add_layer(layer)
        ss.cycles.append(cycle)

        state = DummyState(strategy_state=ss.to_dict())
        result = s.on_tick(tick=_tick(T0 + timedelta(minutes=1), "149.90", "149.92"), state=state)

        assert result.should_stop is True
        assert result.is_error is True
        assert "Grid ordering violation" in (result.stop_reason or "")
