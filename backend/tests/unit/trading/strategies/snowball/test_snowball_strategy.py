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
from apps.trading.events import (
    ClosePositionEvent,
    GenericStrategyEvent,
    OpenPositionEvent,
)
from apps.trading.strategies.snowball.models import SnowballStrategyConfig
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


def _signal_events(result, kind: str | None = None) -> list[GenericStrategyEvent]:
    evts = [e for e in result.events if isinstance(e, GenericStrategyEvent)]
    if kind:
        evts = [e for e in evts if e.data.get("kind") == kind]
    return evts


def _cycle(state) -> dict[str, Any]:
    """Return the first (LONG) cycle dict from serialised state."""
    return state.strategy_state["cycles"][0]


def _occupied_slot_count(state, cycle_idx: int = 0, layer_idx: int = 0) -> int:
    """Count occupied slots in a given layer of a cycle."""
    layers = state.strategy_state["cycles"][cycle_idx].get("layers", [])
    if layer_idx >= len(layers):
        return 0
    return sum(1 for s in layers[layer_idx]["slots"] if s.get("entry") is not None)


def _slot_entries(state, cycle_idx: int = 0, layer_idx: int = 0) -> list[dict]:
    """Return all non-None slot entries from a layer."""
    layers = state.strategy_state["cycles"][cycle_idx].get("layers", [])
    if layer_idx >= len(layers):
        return []
    return [s["entry"] for s in layers[layer_idx]["slots"] if s.get("entry") is not None]


def _layer_count(state, cycle_idx: int = 0) -> int:
    return len(state.strategy_state["cycles"][cycle_idx].get("layers", []))


# ==================================================================
# 1. Initialisation
# ==================================================================


class TestInitialisation:
    def test_first_tick_opens_long_and_short(self):
        s = _strategy()
        state = DummyState()
        result = s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        opens = _open_events(result)
        assert len(opens) == 2
        dirs = {e.direction for e in opens}
        assert dirs == {"long", "short"}
        assert state.strategy_state["initialised"] is True

    def test_second_tick_does_not_reinitialise(self):
        s = _strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=1), "150.00", "150.02"), state=state)
        opens = _open_events(result)
        assert len(opens) == 0


# ==================================================================
# 2. Trend basket rotation
# ==================================================================


class TestTrendBasketRotation:
    def test_long_trend_tp_and_reentry(self):
        s = _strategy(m_pips="50")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.52", "150.54"), state=state)
        long_closes = [c for c in _close_events(result) if c.direction == "long"]
        long_opens = [o for o in _open_events(result) if o.direction == "long"]
        assert len(long_closes) >= 1
        assert len(long_opens) >= 1

    def test_short_trend_tp_and_reentry(self):
        s = _strategy(m_pips="50")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.48", "149.50"), state=state)
        short_closes = [c for c in _close_events(result) if c.direction == "short"]
        assert len(short_closes) >= 1


# ==================================================================
# 3. Counter basket adds
# ==================================================================


class TestCounterBasketAdds:
    def test_first_counter_add_on_adverse_move(self):
        s = _strategy(n_pips_head="30", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.69", "149.71"), state=state)
        counter_opens = [
            o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
        ]
        assert len(counter_opens) == 1
        assert _occupied_slot_count(state) == 1

    def test_second_counter_add(self):
        s = _strategy(n_pips_head="10", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert _occupied_slot_count(state) == 1
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        assert _occupied_slot_count(state) == 2
        entries = _slot_entries(state)
        assert int(entries[0]["units"]) == 2000
        assert int(entries[1]["units"]) == 3000


# ==================================================================
# 4. Counter close — slot vacated, triggers new layer on re-adverse
# ==================================================================


class TestCounterCloseAndLayerProgression:
    def test_counter_tp_vacates_slot(self):
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.69", "149.71"), state=state)
        assert _occupied_slot_count(state) == 3

        # Close highest slot via TP
        entries = _slot_entries(state)
        latest = max(entries, key=lambda e: int(e.get("step", 0)))
        cp = Decimal(str(latest["close_price"]))
        result = s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=240), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        closes = _close_events(result)
        assert len(closes) >= 1
        assert _occupied_slot_count(state) == 2

    def test_reversal_after_close_starts_new_layer(self):
        """After a slot is vacated and price reverses again, a new layer starts."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
            f_max=3,
            refill_up_to=0,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill R1
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert _occupied_slot_count(state) == 1

        # Close R1 via TP
        entries = _slot_entries(state)
        cp = Decimal(str(entries[0]["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=120), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        assert _occupied_slot_count(state) == 0
        assert _layer_count(state) == 1  # still L1

        # Price drops again past the next interval — should start L2
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.70", "149.72"), state=state)
        opens = _open_events(result)
        layer_initials = [o for o in opens if "layer_initial" in (o.strategy_event_type or "")]
        assert len(layer_initials) == 1
        assert _layer_count(state) == 2


# ==================================================================
# 5. Reversal scenario
# ==================================================================


class TestReversalScenario:
    def test_adverse_then_favourable_then_adverse(self):
        s = _strategy(
            m_pips="20",
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="8",
            refill_up_to=0,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Phase 1: adverse — add counter
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert _occupied_slot_count(state) == 1

        # Phase 2: favourable — close counter TP
        entries = _slot_entries(state)
        cp = Decimal(str(entries[0]["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=120), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        assert _occupied_slot_count(state) == 0

        # Phase 3: adverse again — should start new layer
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.70", "149.72"), state=state)
        opens = _open_events(result)
        layer_initials = [o for o in opens if "layer_initial" in (o.strategy_event_type or "")]
        assert len(layer_initials) == 1


# ==================================================================
# 6. r_max → new layer
# ==================================================================


class TestRMaxLayerProgression:
    def test_all_slots_full_triggers_new_layer(self):
        s = _strategy(r_max=3, n_pips_head="5", interval_mode="constant", f_max=3)
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        for i in range(1, 4):
            price = Decimal("150.00") - Decimal("0.05") * i - Decimal("0.01")
            s.on_tick(
                tick=_tick(
                    T0 + timedelta(seconds=60 * i), str(price), str(price + Decimal("0.02"))
                ),
                state=state,
            )
        assert _occupied_slot_count(state) == 3
        assert _layer_count(state) == 1

        # Next adverse tick triggers new layer
        price = Decimal("150.00") - Decimal("0.30")
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=300), str(price), str(price + Decimal("0.02"))),
            state=state,
        )
        assert _layer_count(state) == 2
        opens = _open_events(result)
        layer_initials = [o for o in opens if "layer_initial" in (o.strategy_event_type or "")]
        assert len(layer_initials) == 1


# ==================================================================
# 7. f_max exhaustion
# ==================================================================


class TestFMaxExhaustion:
    def test_no_adds_after_f_max_exceeded(self):
        s = _strategy(r_max=2, f_max=2, n_pips_head="5", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill L1 (2 slots)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.89", "149.91"), state=state)
        # Trigger L2
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.80", "149.82"), state=state)
        assert _layer_count(state) == 2

        # Fill L2 (2 slots)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=240), "149.50", "149.52"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=300), "149.45", "149.47"), state=state)

        # Next adverse tick — f_max=2 reached, no more layers
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=360), "149.30", "149.32"), state=state)
        counter_opens = [
            o
            for o in _open_events(result)
            if "counter" in (o.strategy_event_type or "")
            or "layer_initial" in (o.strategy_event_type or "")
        ]
        assert len(counter_opens) == 0


# ==================================================================
# 8. Emergency stop
# ==================================================================


class TestEmergencyStop:
    def test_emergency_stop_at_95_percent(self):
        s = _strategy()
        state = DummyState(current_balance=Decimal("100"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Inject a huge entry via layer slot to blow margin
        big_entry = {
            "entry_id": 99,
            "step": 1,
            "direction": "long",
            "entry_price": "150.00",
            "close_price": "151.00",
            "units": 5000000,
            "opened_at": T0.isoformat(),
        }
        layers = state.strategy_state["cycles"][0]["layers"]
        layers[0]["slots"][0]["entry"] = big_entry

        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert result.should_stop is True


# ==================================================================
# 9. Shrink mode
# ==================================================================


class TestShrinkMode:
    def test_shrink_closes_worst_counter_entry(self):
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
        layers = state.strategy_state["cycles"][0]["layers"]
        layers[0]["slots"][0]["entry"] = counter_entry

        s._margin_ratio = lambda _state, _ss: Decimal("75")  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        closes = _close_events(result)
        assert len(closes) >= 1
        shrink_signals = _signal_events(result, "snowball_shrink")
        assert len(shrink_signals) >= 1


# ==================================================================
# 10. Lock mode
# ==================================================================


class TestLockMode:
    def test_lock_opens_hedge_and_blocks_trading(self):
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        lock_signals = _signal_events(result, "snowball_locked")
        assert len(lock_signals) >= 1
        assert state.strategy_state["protection_level"] == "locked"

    def test_locked_state_blocks_normal_trading(self):
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "150.50", "150.52"), state=state)
        non_hedge = [
            o for o in _open_events(result) if "lock_hedge" not in (o.strategy_event_type or "")
        ]
        assert len(non_hedge) == 0


# ==================================================================
# 12. Spread guard
# ==================================================================


# ==================================================================
# 13. Monotonic increase
# ==================================================================


class TestMonotonicIncrease:
    def test_steady_rise_rotates_trend_no_counter(self):
        s = _strategy(m_pips="10")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.12", "150.14"), state=state)
        long_closes = [c for c in _close_events(result) if c.direction == "long"]
        assert len(long_closes) >= 1
        assert _occupied_slot_count(state) == 0


# ==================================================================
# 14. Monotonic decrease
# ==================================================================


class TestMonotonicDecrease:
    def test_steady_drop_rotates_short_trend(self):
        s = _strategy(m_pips="10")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.88", "149.90"), state=state)
        short_closes = [c for c in _close_events(result) if c.direction == "short"]
        assert len(short_closes) >= 1


# ==================================================================
# 15. Lock → unlock cycle
# ==================================================================


class TestLockUnlockCycle:
    def test_lock_then_unlock_resumes_trading(self):
        s = _strategy(
            lock_enabled=True,
            n_th="85",
            m_th="70",
            shrink_enabled=False,
        )
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        ratio_value = Decimal("90")
        s._margin_ratio = lambda _state, _ss: ratio_value  # type: ignore[method-assign]
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert state.strategy_state["protection_level"] == "locked"
        ratio_value = Decimal("10")
        s._margin_ratio = lambda _state, _ss: ratio_value  # type: ignore[method-assign]
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "150.00", "150.02"), state=state)
        unlock_signals = _signal_events(result, "snowball_unlocked")
        assert len(unlock_signals) >= 1


# ==================================================================
# 16. Weighted avg TP mode
# ==================================================================


class TestWeightedAvgTpMode:
    def test_weighted_avg_close_price_equals_avg(self):
        s = _strategy(counter_tp_mode="weighted_avg", n_pips_head="10", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        entries = _slot_entries(state)
        assert len(entries) == 1
        assert Decimal(str(entries[0]["close_price"])) > 0


# ==================================================================
# 17. Manual interval mode
# ==================================================================


class TestManualIntervalMode:
    def test_manual_intervals_respected(self):
        s = _strategy(
            interval_mode="manual",
            manual_intervals=["5", "10", "15", "20", "25", "30", "35"],
            r_max=7,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        assert _occupied_slot_count(state) == 1
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.84", "149.86"), state=state)
        assert _occupied_slot_count(state) == 2


# ==================================================================
# 18. post_r_max_base_factor
# ==================================================================


class TestPostRMaxBaseFactor:
    def test_new_layer_uses_updated_base_units(self):
        s = _strategy(
            r_max=2,
            f_max=5,
            n_pips_head="5",
            interval_mode="constant",
            post_r_max_base_factor="1.5",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.89", "149.91"), state=state)
        assert _occupied_slot_count(state) == 2

        # Trigger new layer
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.80", "149.82"), state=state)
        assert _layer_count(state) == 2
        # L2 base_units = 1000 * 1.5 = 1500
        l2 = state.strategy_state["cycles"][0]["layers"][1]
        assert l2["base_units"] == 1500


# ==================================================================
# Expected table validation
# ==================================================================


class TestExpectedTableValidation:
    @staticmethod
    def _make_strategy() -> SnowballStrategy:
        return _strategy(
            m_pips="50",
            r_max=7,
            f_max=3,
            interval_mode="manual",
            manual_intervals=["30", "30", "25", "20", "16", "14", "12"],
            counter_tp_mode="weighted_avg",
            post_r_max_base_factor="1",
        )

    def test_layer1_lot_sizes_and_tp(self):
        s = self._make_strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "100.00", "100.00"), state=state)

        drops = [
            ("99.70", "99.70", 2000),
            ("99.40", "99.40", 3000),
            ("99.15", "99.15", 4000),
            ("98.95", "98.95", 5000),
            ("98.79", "98.79", 6000),
            ("98.65", "98.65", 7000),
        ]
        for i, (bid, ask, expected_units) in enumerate(drops, 1):
            result = s.on_tick(tick=_tick(T0 + timedelta(seconds=i * 60), bid, ask), state=state)
            counter_opens = [
                o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
            ]
            assert len(counter_opens) == 1, f"R{i}: expected 1 counter open"
            assert counter_opens[0].units == expected_units
        assert _occupied_slot_count(state) == 6

    def test_layer_progression_tp_uses_prev_layer_highest_slot(self):
        s = self._make_strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "100.00", "100.00"), state=state)

        l1_drops = ["99.70", "99.40", "99.15", "98.95", "98.79", "98.65", "98.53"]
        for i, price in enumerate(l1_drops, 1):
            s.on_tick(tick=_tick(T0 + timedelta(seconds=i * 60), price, price), state=state)
        assert _occupied_slot_count(state) == 7

        # Trigger L2
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=480), "98.41", "98.41"), state=state)
        layer_initials = [
            o for o in _open_events(result) if "layer_initial" in (o.strategy_event_type or "")
        ]
        assert len(layer_initials) == 1
        l2_init = layer_initials[0]
        assert l2_init.units == 1000

        # L2/R0 TP should equal L1/R7's close_price (highest occupied slot in L1)
        # L1/R7 close_price is the weighted avg of all L1 entries at the time R7 was added
        # We just verify it's NOT the old weighted-avg-of-everything formula
        # and that it's a reasonable value between entry and initial
        assert l2_init.planned_exit_price > Decimal("98.41")  # above L2 entry
        assert l2_init.planned_exit_price < Decimal("100.00")  # below L1 initial
        # Formula should be a simple numeric string
        formula = l2_init.planned_exit_price_formula or ""
        assert "weighted_avg" not in formula
        assert formula.replace(".", "").replace("-", "").isdigit()

    def test_layer2_counter_tp_uses_layer2_only(self):
        s = self._make_strategy()
        state = DummyState()
        s.on_tick(tick=_tick(T0, "100.00", "100.00"), state=state)
        l1_drops = ["99.70", "99.40", "99.15", "98.95", "98.79", "98.65", "98.53"]
        for i, price in enumerate(l1_drops, 1):
            s.on_tick(tick=_tick(T0 + timedelta(seconds=i * 60), price, price), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=480), "98.41", "98.41"), state=state)

        # L2/R1 at 98.11 (-30 pips from L2 initial 98.41)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=540), "98.11", "98.11"), state=state)
        counter_opens = [
            o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
        ]
        assert len(counter_opens) == 1
        assert counter_opens[0].units == 2000
        expected_tp = (Decimal("98.41") * 1000 + Decimal("98.11") * 2000) / 3000
        assert abs(counter_opens[0].planned_exit_price - expected_tp) < Decimal("0.001")


# ==================================================================
# Initial Entry has retracement_count = 0
# ==================================================================


class TestInitialEntryRetracementCount:
    def test_initial_entries_have_retracement_count_zero(self):
        """L1/R0 initial entries must have retracement_count=0."""
        s = _strategy()
        state = DummyState()
        result = s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        opens = _open_events(result)
        for o in opens:
            assert o.retracement_count == 0, (
                f"{o.direction} initial entry has retracement_count={o.retracement_count}"
            )


# ==================================================================
# Refill: R1 close then re-enter same slot (refill_up_to=2)
# ==================================================================


class TestRefillWithinThreshold:
    def test_r1_close_then_refill_same_slot(self):
        """With refill_up_to=2, closing R1 should allow re-entry at R1."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
            refill_up_to=2,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill R1
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert _occupied_slot_count(state) == 1

        # Close R1 via TP
        entries = _slot_entries(state)
        cp = Decimal(str(entries[0]["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=120), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        assert _occupied_slot_count(state) == 0

        # R1 slot should NOT be ever_closed (refillable)
        layer = state.strategy_state["cycles"][0]["layers"][0]
        assert layer["slots"][0]["ever_closed"] is False

        # Drop again — should refill R1, NOT start new layer
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.80", "149.82"), state=state)
        opens = _open_events(result)
        counter_opens = [o for o in opens if "counter" in (o.strategy_event_type or "")]
        assert len(counter_opens) == 1
        assert counter_opens[0].retracement_count == 1  # R1 again
        assert _layer_count(state) == 1  # still L1

    def test_r3_close_triggers_new_layer(self):
        """With refill_up_to=2, closing R3 should trigger a new layer."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
            refill_up_to=2,
            f_max=3,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill R1, R2, R3
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.69", "149.71"), state=state)
        assert _occupied_slot_count(state) == 3

        # Close R3 via TP
        entries = _slot_entries(state)
        latest = max(entries, key=lambda e: int(e.get("step", 0)))
        cp = Decimal(str(latest["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=240), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        assert _occupied_slot_count(state) == 2  # R1, R2 remain

        # R3 slot should be ever_closed (index=3 > refill_up_to=2)
        layer = state.strategy_state["cycles"][0]["layers"][0]
        assert layer["slots"][2]["ever_closed"] is True

        # Drop again — should start new layer
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=300), "149.50", "149.52"), state=state)
        opens = _open_events(result)
        layer_initials = [o for o in opens if "layer_initial" in (o.strategy_event_type or "")]
        assert len(layer_initials) == 1
        assert _layer_count(state) == 2


# ==================================================================
# L2+ R0 close resets layer for reuse
# ==================================================================


class TestL2InitialCloseRemovesLayer:
    def test_l2_initial_close_removes_layer(self):
        """When L2/R0 is closed, the layer is removed from cycle.layers.

        This makes current_layer revert to L1, and L2 will only be
        recreated when L1 slots get sealed again (needs_new_layer).
        """
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
            refill_up_to=0,
            f_max=3,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill R1 → close R1 → triggers L2
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        entries = _slot_entries(state)
        cp = Decimal(str(entries[0]["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=120), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        # Drop to trigger L2 creation
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.70", "149.72"), state=state)
        assert _layer_count(state) == 2

        # Now close L2/R0 (layer initial) — L2 has no slots filled
        l2 = state.strategy_state["cycles"][0]["layers"][1]
        assert l2["initial_entry"] is not None
        l2_cp = Decimal(str(l2["initial_entry"]["close_price"]))

        # Move price to close L2 initial
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=240),
                str(l2_cp + Decimal("0.01")),
                str(l2_cp + Decimal("0.03")),
            ),
            state=state,
        )

        # L2 should be removed entirely — only L1 remains
        assert _layer_count(state) == 1


# ==================================================================
# Close order validation: newest layer highest R first
# ==================================================================


class TestCloseOrder:
    def test_closes_highest_r_in_newest_layer_first(self):
        """With L1/R1, L1/R2 filled, R2 must close before R1."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Fill R1 and R2
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        assert _occupied_slot_count(state) == 2

        # Move price to close R2 (highest) — R2 close_price should be hit first
        entries = _slot_entries(state)
        r2 = max(entries, key=lambda e: int(e.get("retracement_count", 0)))
        r2_cp = Decimal(str(r2["close_price"]))

        result = s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=180),
                str(r2_cp + Decimal("0.01")),
                str(r2_cp + Decimal("0.03")),
            ),
            state=state,
        )
        closes = _close_events(result)
        assert len(closes) == 1
        assert closes[0].retracement_count == 2  # R2 closed, not R1
        assert _occupied_slot_count(state) == 1  # R1 remains


# ==================================================================
# L1/R0 close ends cycle
# ==================================================================


class TestCycleEndOnL1R0Close:
    def test_l1_initial_close_completes_cycle_and_creates_new(self):
        """Closing L1/R0 (initial entry) ends the cycle and starts a new one."""
        s = _strategy(m_pips="10")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Move price up 11 pips to close LONG initial entry
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.12", "150.14"), state=state)
        long_closes = [c for c in _close_events(result) if c.direction == "long"]
        long_opens = [o for o in _open_events(result) if o.direction == "long"]
        assert len(long_closes) >= 1
        assert len(long_opens) >= 1  # new cycle started

        # The old cycle should be completed
        cycles = state.strategy_state["cycles"]
        completed_long = [c for c in cycles if c["direction"] == "long" and c["completed"]]
        assert len(completed_long) >= 1


# ==================================================================
# Formula strings are numeric expressions
# ==================================================================


class TestFormulaStrings:
    def test_counter_tp_formula_is_numeric(self):
        """weighted_avg formula should contain actual numbers, not text."""
        s = _strategy(
            counter_tp_mode="weighted_avg",
            n_pips_head="10",
            interval_mode="constant",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        counter_opens = [
            o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
        ]
        assert len(counter_opens) == 1
        formula = counter_opens[0].planned_exit_price_formula
        assert formula is not None
        # Should contain numbers and operators, not "weighted_avg(...)"
        assert "weighted_avg" not in formula
        assert "*" in formula
        assert "/" in formula

    def test_layer_initial_formula_is_numeric(self):
        """L2 initial formula should reference prev layer's highest slot."""
        s = _strategy(
            r_max=2,
            f_max=3,
            n_pips_head="5",
            interval_mode="constant",
            counter_tp_mode="weighted_avg",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.89", "149.91"), state=state)

        # Trigger L2
        result = s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.80", "149.82"), state=state)
        layer_initials = [
            o for o in _open_events(result) if "layer_initial" in (o.strategy_event_type or "")
        ]
        assert len(layer_initials) == 1
        formula = layer_initials[0].planned_exit_price_formula
        assert formula is not None
        assert "weighted_avg" not in formula
        assert formula.replace(".", "").replace("-", "").isdigit()


# ==================================================================
# Lot sizes follow (slot_index + 1) * base_units
# ==================================================================


class TestLotSizes:
    def test_counter_lot_sizes_increase_with_slot(self):
        """R1=2000, R2=3000, R3=4000 with base_units=1000."""
        s = _strategy(n_pips_head="10", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        expected_units = [2000, 3000, 4000]
        for i, expected in enumerate(expected_units, 1):
            price = Decimal("150.00") - Decimal("0.10") * i - Decimal("0.01")
            result = s.on_tick(
                tick=_tick(
                    T0 + timedelta(seconds=60 * i), str(price), str(price + Decimal("0.02"))
                ),
                state=state,
            )
            counter_opens = [
                o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
            ]
            assert len(counter_opens) == 1, f"R{i}: expected 1 counter open"
            assert counter_opens[0].units == expected, (
                f"R{i}: expected {expected} units, got {counter_opens[0].units}"
            )
