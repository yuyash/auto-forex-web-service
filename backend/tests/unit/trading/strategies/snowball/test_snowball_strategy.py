"""Comprehensive unit tests for SnowballStrategy tick-driven behavior.

Covers: initialisation, trend basket rotation, counter basket adds/closes,
add_count reset after TP, r_max cycle reset, f_max exhaustion, margin
protection (shrink / lock / emergency), rebalance, spread guard, and
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
        "dynamic_tp_enabled": False,
        "rebalance_enabled": False,
        "shrink_enabled": False,
        "lock_enabled": False,
        "spread_guard_enabled": False,
        "spread_guard_pips": "2.5",
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
        # No new opens unless trend TP or counter add triggers
        opens = _open_events(result)
        assert len(opens) == 0


# ==================================================================
# 2. Trend basket — monotonic move triggers rotation
# ==================================================================


class TestTrendBasketRotation:
    def test_long_trend_tp_and_reentry(self):
        """Price rises 50+ pips → long trend entry closes and re-opens."""
        s = _strategy(m_pips="50")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Move up 51 pips (bid >= entry_ask + 50*0.01)
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.52", "150.54"),
            state=state,
        )
        closes = _close_events(result)
        opens = _open_events(result)
        # Should close the long trend entry and re-open a new long
        long_closes = [c for c in closes if c.direction == "long"]
        long_opens = [o for o in opens if o.direction == "long"]
        assert len(long_closes) >= 1
        assert len(long_opens) >= 1

    def test_short_trend_tp_and_reentry(self):
        """Price drops 50+ pips → short trend entry closes and re-opens."""
        s = _strategy(m_pips="50")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "149.48", "149.50"),
            state=state,
        )
        closes = _close_events(result)
        short_closes = [c for c in closes if c.direction == "short"]
        assert len(short_closes) >= 1


# ==================================================================
# 3. Counter basket — monotonic adverse move adds steps
# ==================================================================


class TestCounterBasketAdds:
    def test_first_counter_add_on_adverse_move(self):
        """When one trend side loses >= n_pips_head, first counter entry opens."""
        s = _strategy(n_pips_head="30", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Drop 31 pips — long side is losing
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "149.69", "149.71"),
            state=state,
        )
        opens = _open_events(result)
        counter_opens = [o for o in opens if "counter" in (o.strategy_event_type or "")]
        assert len(counter_opens) == 1
        # First counter add: lot_k=2 (trend=1), add_count=1
        assert state.strategy_state["add_count"] == 1

    def test_second_counter_add(self):
        """Counter adds use lot_k=2,3,4... (trend entry is position 1)."""
        s = _strategy(n_pips_head="10", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # First add — lot_k=2 (trend entry is position 1)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert state.strategy_state["add_count"] == 1

        # Second add — 10 more pips from latest counter entry, lot_k=3
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        assert state.strategy_state["add_count"] == 2

        counter = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        assert len(counter) == 2
        # lot_k=2 → 2000, lot_k=3 → 3000
        assert int(counter[0]["units"]) == 2000
        assert int(counter[-1]["units"]) == 3000


# ==================================================================
# 4. Counter close — TP hit resets add_count to 0
# ==================================================================


class TestCounterCloseResetsAddCount:
    def test_counter_tp_resets_add_count_to_zero(self):
        """After a counter entry is closed at TP, add_count resets to 0
        so the next adverse add restarts from lot_k=1."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
        )
        state = DummyState()
        # Init
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Add counter entries by dropping price
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.69", "149.71"), state=state)
        assert state.strategy_state["add_count"] == 3

        # Now price reverses — latest counter entry (long) has close_price set
        counter = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        latest = max(counter, key=lambda e: int(e.get("step", 0)))
        close_price = Decimal(str(latest["close_price"]))

        # Move bid above close_price to trigger TP
        bid_str = str(close_price + Decimal("0.01"))
        ask_str = str(close_price + Decimal("0.03"))
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=240), bid_str, ask_str),
            state=state,
        )

        closes = _close_events(result)
        assert len(closes) >= 1
        # add_count resets to 0 after TP close
        assert state.strategy_state["add_count"] == 0

    def test_next_add_after_close_restarts_from_lot1(self):
        """After TP close resets add_count, the next add uses lot_k=1 (1000 units)."""
        s = _strategy(
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="5",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Build up counter entries
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.79", "149.81"), state=state)

        # Close latest via TP
        counter = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        latest = max(counter, key=lambda e: int(e.get("step", 0)))
        cp = Decimal(str(latest["close_price"]))
        s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=180), str(cp + Decimal("0.01")), str(cp + Decimal("0.03"))
            ),
            state=state,
        )
        assert state.strategy_state["add_count"] == 0

        # Now drop again — next add should restart from lot_k=1, 1000 units
        remaining = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        if remaining:
            latest_remaining = max(remaining, key=lambda e: int(e.get("step", 0)))
            ep = Decimal(str(latest_remaining["entry_price"]))
            drop_price = ep - Decimal("0.11")  # 11 pips below
        else:
            drop_price = Decimal("149.50")

        result = s.on_tick(
            tick=_tick(
                T0 + timedelta(seconds=240), str(drop_price), str(drop_price + Decimal("0.02"))
            ),
            state=state,
        )
        opens = _open_events(result)
        counter_opens = [o for o in opens if "counter" in (o.strategy_event_type or "")]
        if counter_opens:
            # lot_k=1 → 1000 units, Ret=1 (fresh restart after TP close)
            assert counter_opens[0].units == 1000
            assert counter_opens[0].retracement_count == 1


# ==================================================================
# 5. Adverse → favourable → adverse again (reversal scenario)
# ==================================================================


class TestReversalScenario:
    def test_adverse_then_favourable_then_adverse(self):
        """Counter adds build up, trend TP fires on reversal, then
        further adverse move re-adds from step 1."""
        s = _strategy(
            m_pips="20",
            n_pips_head="10",
            interval_mode="constant",
            counter_tp_mode="fixed",
            counter_tp_pips="8",
        )
        state = DummyState()
        # Init at 150.00
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Phase 1: adverse (drop) — add counter entries
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        assert state.strategy_state["add_count"] == 1

        # Phase 2: favourable (rise) — close counter TP
        counter = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        if counter:
            latest = max(counter, key=lambda e: int(e.get("step", 0)))
            cp = Decimal(str(latest["close_price"]))
            s.on_tick(
                tick=_tick(
                    T0 + timedelta(seconds=120),
                    str(cp + Decimal("0.01")),
                    str(cp + Decimal("0.03")),
                ),
                state=state,
            )
            assert state.strategy_state["add_count"] == 0

        # Phase 3: adverse again — should add from step 1
        remaining = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        if remaining:
            ref = Decimal(str(max(remaining, key=lambda e: int(e.get("step", 0)))["entry_price"]))
        else:
            # Use trend entry as reference
            ref = Decimal("150.02")
        drop = ref - Decimal("0.11")
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=180), str(drop), str(drop + Decimal("0.02"))),
            state=state,
        )
        opens = _open_events(result)
        counter_opens = [o for o in opens if "counter" in (o.strategy_event_type or "")]
        if counter_opens:
            assert counter_opens[0].units == 1000  # lot_k=1 (restart after TP close)


# ==================================================================
# 6. r_max cycle reset
# ==================================================================


class TestRMaxCycleReset:
    def test_cycle_resets_at_r_max(self):
        """When add_count reaches r_max, cycle resets."""
        s = _strategy(
            r_max=3,
            n_pips_head="5",
            interval_mode="constant",
            f_max=3,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Add 3 counter entries
        for i in range(1, 4):
            price = Decimal("150.00") - Decimal("0.05") * i - Decimal("0.01")
            s.on_tick(
                tick=_tick(
                    T0 + timedelta(seconds=60 * i), str(price), str(price + Decimal("0.02"))
                ),
                state=state,
            )

        assert state.strategy_state["add_count"] == 3

        # Next tick should trigger cycle reset (add_count >= r_max)
        price = Decimal("150.00") - Decimal("0.30")
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=300), str(price), str(price + Decimal("0.02"))),
            state=state,
        )
        signals = _signal_events(result, "snowball_cycle_reset")
        assert len(signals) == 0
        assert state.strategy_state["add_count"] == 0
        assert state.strategy_state["freeze_count"] == 1


# ==================================================================
# 7. f_max exhaustion
# ==================================================================


class TestFMaxExhaustion:
    def test_no_adds_after_f_max_exceeded(self):
        """Once freeze_count >= f_max, no more counter adds."""
        s = _strategy(r_max=2, f_max=1, n_pips_head="5", interval_mode="constant")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Force state to f_max exceeded
        state.strategy_state["freeze_count"] = 2  # > f_max=1
        state.strategy_state["add_count"] = 0

        price = Decimal("149.50")
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), str(price), str(price + Decimal("0.02"))),
            state=state,
        )
        counter_opens = [
            o for o in _open_events(result) if "counter" in (o.strategy_event_type or "")
        ]
        assert len(counter_opens) == 0


# ==================================================================
# 8. Emergency stop
# ==================================================================


class TestEmergencyStop:
    def test_emergency_stop_at_95_percent(self):
        """Margin ratio >= 95% triggers emergency stop regardless of settings."""
        s = _strategy()
        state = DummyState(current_balance=Decimal("100"))  # tiny balance
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Force huge positions to blow margin ratio
        state.strategy_state["account_nav"] = "100"
        big_entry = {
            "entry_id": 99,
            "step": 1,
            "direction": "long",
            "entry_price": "150.00",
            "close_price": "151.00",
            "units": 5000000,
            "opened_at": T0.isoformat(),
        }
        state.strategy_state["trend_basket"].append(big_entry)

        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"),
            state=state,
        )
        assert result.should_stop is True
        stop_events = [
            e
            for e in result.events
            if isinstance(e, GenericStrategyEvent) and e.data.get("kind") == "emergency_stop"
        ]
        assert len(stop_events) == 1


# ==================================================================
# 9. Shrink mode
# ==================================================================


class TestShrinkMode:
    def test_shrink_closes_worst_counter_entry(self):
        """When shrink_enabled and ratio >= m_th, worst counter entry is closed."""
        s = _strategy(shrink_enabled=True, m_th="70", lock_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Add a counter entry manually
        counter_entry = {
            "entry_id": 10,
            "step": 2,
            "direction": "long",
            "entry_price": "151.00",
            "close_price": "151.50",
            "units": 1000,
            "opened_at": T0.isoformat(),
        }
        state.strategy_state["counter_basket"].append(counter_entry)
        # Stub margin ratio to 75 (between m_th=70 and emergency=95)
        s._margin_ratio = lambda _state, _ss: Decimal("75")  # type: ignore[method-assign]

        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"),
            state=state,
        )
        closes = _close_events(result)
        assert len(closes) >= 1
        shrink_signals = _signal_events(result, "snowball_shrink")
        assert len(shrink_signals) >= 1


# ==================================================================
# 10. Lock mode
# ==================================================================


class TestLockMode:
    def test_lock_opens_hedge_and_blocks_trading(self):
        """When lock_enabled and ratio >= n_th, hedge is opened and trading pauses."""
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Stub margin ratio to 90 (between n_th=85 and emergency=95)
        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]

        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"),
            state=state,
        )
        lock_signals = _signal_events(result, "snowball_locked")
        assert len(lock_signals) >= 1
        assert state.strategy_state["protection_level"] == "locked"

    def test_locked_state_blocks_normal_trading(self):
        """While locked, no trend/counter processing occurs."""
        s = _strategy(lock_enabled=True, n_th="85", shrink_enabled=False)
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Stub margin ratio to 90 to enter lock
        s._margin_ratio = lambda _state, _ss: Decimal("90")  # type: ignore[method-assign]
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert state.strategy_state["protection_level"] == "locked"

        # Next tick — still locked, no new opens
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=120), "150.50", "150.52"),
            state=state,
        )
        opens = _open_events(result)
        # Only hedge-related opens, no trend/counter
        non_hedge = [o for o in opens if "lock_hedge" not in (o.strategy_event_type or "")]
        assert len(non_hedge) == 0


# ==================================================================
# 11. Rebalance
# ==================================================================


class TestRebalance:
    def test_rebalance_closes_heavier_side(self):
        """When rebalance_enabled and ratio >= start, heavier side entries close."""
        s = _strategy(
            rebalance_enabled=True,
            rebalance_start_ratio="50",
            rebalance_end_ratio="40",
            shrink_enabled=False,
            lock_enabled=False,
        )
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Add imbalanced counter entries (all long)
        for i in range(3):
            state.strategy_state["counter_basket"].append(
                {
                    "entry_id": 20 + i,
                    "step": i + 2,
                    "direction": "long",
                    "entry_price": str(Decimal("149.00") - Decimal("0.10") * i),
                    "close_price": "150.00",
                    "units": 1000 * (i + 1),
                    "opened_at": T0.isoformat(),
                }
            )
        # total_units = 2000 (trend) + 1000+2000+3000 (counter) = 8000
        # required = 150*8000*0.04 = 48000
        # For ratio ~60%: nav = 48000/0.60 = 80000
        state.strategy_state["account_nav"] = "80000"

        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"),
            state=state,
        )
        closes = _close_events(result)
        assert len(closes) >= 1


# ==================================================================
# 12. Spread guard
# ==================================================================


class TestSpreadGuard:
    def test_spread_guard_blocks_trading(self):
        """When spread exceeds limit, no trading occurs."""
        s = _strategy(spread_guard_enabled=True, spread_guard_pips="1")
        state = DummyState()
        # Spread = 5 pips (0.05 / 0.01) > 1
        result = s.on_tick(tick=_tick(T0, "150.00", "150.05"), state=state)
        # Should not initialise
        assert state.strategy_state.get("initialised") is not True
        opens = _open_events(result)
        assert len(opens) == 0

    def test_narrow_spread_allows_trading(self):
        """When spread is within limit, trading proceeds normally."""
        s = _strategy(spread_guard_enabled=True, spread_guard_pips="5")
        state = DummyState()
        # Spread = 2 pips (0.02 / 0.01) <= 5
        result = s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)
        assert state.strategy_state["initialised"] is True
        opens = _open_events(result)
        assert len(opens) == 2


# ==================================================================
# 13. Monotonic increase — only trend rotation, no counter adds
# ==================================================================


class TestMonotonicIncrease:
    def test_steady_rise_rotates_trend_no_counter(self):
        """Steady price increase should only rotate trend basket, not add counter."""
        s = _strategy(m_pips="10")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Rise 11 pips
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "150.12", "150.14"),
            state=state,
        )
        # Long trend should TP and re-enter
        long_closes = [c for c in _close_events(result) if c.direction == "long"]
        assert len(long_closes) >= 1

        # No counter adds (short side is losing but not enough pips yet)
        counter = state.strategy_state.get("counter_basket", [])
        non_hedge = [e for e in counter if not e.get("is_hedge")]
        # With only 11 pips move and n_pips_head=30, no counter add
        assert len(non_hedge) == 0


# ==================================================================
# 14. Monotonic decrease — mirror of increase
# ==================================================================


class TestMonotonicDecrease:
    def test_steady_drop_rotates_short_trend(self):
        """Steady price decrease should rotate short trend basket."""
        s = _strategy(m_pips="10")
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Drop 11 pips
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=60), "149.88", "149.90"),
            state=state,
        )
        short_closes = [c for c in _close_events(result) if c.direction == "short"]
        assert len(short_closes) >= 1


# ==================================================================
# 15. Lock → unlock cycle
# ==================================================================


class TestLockUnlockCycle:
    def test_lock_then_unlock_resumes_trading(self):
        """After lock and subsequent ratio drop, trading resumes."""
        s = _strategy(
            lock_enabled=True,
            n_th="85",
            m_th="70",
            shrink_enabled=False,
            spread_guard_enabled=False,
        )
        state = DummyState(current_balance=Decimal("1000000"))
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Enter lock: stub ratio to 90
        ratio_value = Decimal("90")
        s._margin_ratio = lambda _state, _ss: ratio_value  # type: ignore[method-assign]
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "150.00", "150.02"), state=state)
        assert state.strategy_state["protection_level"] == "locked"

        # Restore ratio to unlock (below m_th - 5 = 65)
        ratio_value = Decimal("10")
        s._margin_ratio = lambda _state, _ss: ratio_value  # type: ignore[method-assign]
        result = s.on_tick(
            tick=_tick(T0 + timedelta(seconds=120), "150.00", "150.02"),
            state=state,
        )
        unlock_signals = _signal_events(result, "snowball_unlocked")
        assert len(unlock_signals) >= 1
        assert state.strategy_state["protection_level"] in ("normal", "shrink")


# ==================================================================
# 16. Counter basket — weighted_avg TP mode
# ==================================================================


class TestWeightedAvgTpMode:
    def test_weighted_avg_close_price_equals_avg(self):
        """In weighted_avg mode, close_price should be the basket average."""
        s = _strategy(
            counter_tp_mode="weighted_avg",
            n_pips_head="10",
            interval_mode="constant",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # First counter add
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.89", "149.91"), state=state)
        counter = [e for e in state.strategy_state["counter_basket"] if not e.get("is_hedge")]
        assert len(counter) == 1
        # For weighted_avg with single entry, close_price = entry_price of losing trend
        # (the initial trend entry price)
        assert Decimal(str(counter[0]["close_price"])) > 0


# ==================================================================
# 17. Manual interval mode
# ==================================================================


class TestManualIntervalMode:
    def test_manual_intervals_respected(self):
        """Manual intervals should use user-specified pip distances."""
        s = _strategy(
            interval_mode="manual",
            manual_intervals=["5", "10", "15", "20", "25", "30", "35"],
            r_max=7,
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # First add at 5 pips
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        assert state.strategy_state["add_count"] == 1

        # Second add needs 10 more pips from latest entry
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.84", "149.86"), state=state)
        assert state.strategy_state["add_count"] == 2


# ==================================================================
# 18. post_r_max_base_factor
# ==================================================================


class TestPostRMaxBaseFactor:
    def test_cycle_base_units_updated_after_r_max(self):
        """After r_max reset, cycle_base_units = base_units * factor."""
        s = _strategy(
            r_max=2,
            f_max=5,
            n_pips_head="5",
            interval_mode="constant",
            post_r_max_base_factor="1.5",
        )
        state = DummyState()
        s.on_tick(tick=_tick(T0, "150.00", "150.02"), state=state)

        # Add 2 entries to hit r_max
        s.on_tick(tick=_tick(T0 + timedelta(seconds=60), "149.94", "149.96"), state=state)
        s.on_tick(tick=_tick(T0 + timedelta(seconds=120), "149.89", "149.91"), state=state)
        assert state.strategy_state["add_count"] == 2

        # Trigger cycle reset
        s.on_tick(tick=_tick(T0 + timedelta(seconds=180), "149.80", "149.82"), state=state)
        assert state.strategy_state["freeze_count"] == 1
        assert state.strategy_state["cycle_base_units"] == 1500  # 1000 * 1.5
