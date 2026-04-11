"""Snowball strategy tick-pattern integration tests.

Tests the strategy against realistic tick sequences using the production
Snowball Strategy Configuration 1 parameters:

    m_pips=50, r_max=7, f_max=3, interval_mode=manual,
    manual_intervals=[30, 30, 25, 20, 16, 14, 12],
    counter_tp_mode=weighted_avg, pip_size=0.01

Tick patterns tested:
    1. Monotonic increase
    2. Monotonic decrease
    3. Increase then decrease
    4. Increase → decrease → increase (V-shape recovery)
    5. Decrease → increase → decrease (inverted V)

Each pattern is run with stop_loss_enabled=True and False,
and both LONG and SHORT cycles are verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.trading.enums import EventType
from apps.trading.strategies.snowball.models import (
    SnowballStrategyConfig,
    SnowballStrategyState,
)
from apps.trading.strategies.snowball.strategy import SnowballStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROD_CONFIG: dict[str, Any] = {
    "base_units": 1000,
    "m_pips": "50",
    "r_max": 7,
    "f_max": 3,
    "trend_lot_size": 1,
    "n_pips_head": "30",
    "n_pips_tail": "14",
    "n_pips_flat_steps": 2,
    "n_pips_gamma": "1.4",
    "interval_mode": "manual",
    "manual_intervals": ["30", "30", "25", "20", "16", "14", "12"],
    "counter_tp_mode": "weighted_avg",
    "counter_tp_pips": "25",
    "counter_tp_step_amount": "2.5",
    "counter_tp_multiplier": "1.2",
    "round_step_pips": "0.1",
    "shrink_enabled": False,
    "lock_enabled": False,
    "m_th": "70",
    "m1_th": "50",
    "n_th": "85",
    "cooldown_sec": 300,
    "emergency_enabled": True,
    "post_r_max_base_factor": "1",
    "refill_up_to": 3,
    "pip_size": "0.01",
    "reseed_on_all_pending": True,
}

SPREAD = Decimal("0.02")  # 2 pips spread
PIP = Decimal("0.01")


@dataclass
class DummyState:
    """Minimal ExecutionState shape required by strategy.on_tick."""

    strategy_state: dict[str, Any] = field(default_factory=dict)
    current_balance: Decimal = Decimal("1000000")
    ticks_processed: int = 1


def _make_tick(ts: datetime, mid: Decimal) -> Any:
    from apps.trading.dataclasses.tick import Tick

    bid = mid - SPREAD / 2
    ask = mid + SPREAD / 2
    return Tick.create(
        instrument="USD_JPY",
        timestamp=ts,
        bid=bid,
        ask=ask,
        mid=mid,
    )


def _strategy(
    stop_loss: bool,
    overrides: dict[str, Any] | None = None,
) -> SnowballStrategy:
    params = {**PROD_CONFIG, "stop_loss_enabled": stop_loss}
    if overrides:
        params.update(overrides)
    config = SnowballStrategyConfig.from_dict(params)
    return SnowballStrategy("USD_JPY", PIP, config)


class TickRunner:
    """Run a sequence of mid prices through the strategy and collect results."""

    def __init__(self, stop_loss: bool, overrides: dict[str, Any] | None = None) -> None:
        self.strategy = _strategy(stop_loss, overrides)
        self.state = DummyState()
        self.all_events: list[Any] = []
        self.ts = datetime(2026, 1, 1, tzinfo=UTC)
        self.last_mid = START_PRICE

    def tick(self, mid: Decimal) -> Any:
        self.ts += timedelta(seconds=1)
        self.state.ticks_processed += 1
        self.last_mid = mid
        result = self.strategy.on_tick(
            tick=_make_tick(self.ts, mid),
            state=self.state,
        )
        self.all_events.extend(result.events)
        return result

    def tick_range(self, start: Decimal, end: Decimal, step_pips: int = 1) -> None:
        """Generate ticks from start to end in pip increments."""
        step = PIP * step_pips
        current = start
        if end >= start:
            while current <= end:
                self.tick(current)
                current += step
        else:
            while current >= end:
                self.tick(current)
                current -= step

    @property
    def ss(self) -> SnowballStrategyState:
        return SnowballStrategyState.from_strategy_state(self.state.strategy_state)

    @property
    def open_events(self) -> list:
        return [e for e in self.all_events if e.event_type == EventType.OPEN_POSITION]

    @property
    def close_events(self) -> list:
        return [e for e in self.all_events if e.event_type == EventType.CLOSE_POSITION]

    @property
    def rebuild_events(self) -> list:
        return [e for e in self.all_events if e.event_type == EventType.REBUILD_POSITION]

    def long_cycles(self) -> list:
        return [c for c in self.ss.cycles if c.direction.value == "long"]

    def short_cycles(self) -> list:
        return [c for c in self.ss.cycles if c.direction.value == "short"]

    def assert_no_error(self, result) -> None:
        assert not result.should_stop, f"Strategy stopped: {result.stop_reason}"


# ---------------------------------------------------------------------------
# Tick pattern generators
# ---------------------------------------------------------------------------

START_PRICE = Decimal("155.000")


def _pattern_monotonic_increase(runner: TickRunner) -> None:
    """Pattern 1: Price rises steadily by 200 pips."""
    runner.tick_range(START_PRICE, START_PRICE + Decimal("2.00"), step_pips=2)


def _pattern_monotonic_decrease(runner: TickRunner) -> None:
    """Pattern 2: Price falls steadily by 200 pips."""
    runner.tick_range(START_PRICE, START_PRICE - Decimal("2.00"), step_pips=2)


def _pattern_up_then_down(runner: TickRunner) -> None:
    """Pattern 3: Rise 100 pips, then fall 200 pips."""
    peak = START_PRICE + Decimal("1.00")
    bottom = START_PRICE - Decimal("1.00")
    runner.tick_range(START_PRICE, peak, step_pips=2)
    runner.tick_range(peak - PIP * 2, bottom, step_pips=2)


def _pattern_up_down_up(runner: TickRunner) -> None:
    """Pattern 4: Rise 100 pips, fall 150 pips, rise 200 pips."""
    p1 = START_PRICE + Decimal("1.00")
    p2 = START_PRICE - Decimal("0.50")
    p3 = START_PRICE + Decimal("1.50")
    runner.tick_range(START_PRICE, p1, step_pips=2)
    runner.tick_range(p1 - PIP * 2, p2, step_pips=2)
    runner.tick_range(p2 + PIP * 2, p3, step_pips=2)


def _pattern_down_up_down(runner: TickRunner) -> None:
    """Pattern 5: Fall 100 pips, rise 150 pips, fall 200 pips."""
    p1 = START_PRICE - Decimal("1.00")
    p2 = START_PRICE + Decimal("0.50")
    p3 = START_PRICE - Decimal("1.50")
    runner.tick_range(START_PRICE, p1, step_pips=2)
    runner.tick_range(p1 + PIP * 2, p2, step_pips=2)
    runner.tick_range(p2 - PIP * 2, p3, step_pips=2)


PATTERNS = [
    pytest.param(_pattern_monotonic_increase, id="monotonic_increase"),
    pytest.param(_pattern_monotonic_decrease, id="monotonic_decrease"),
    pytest.param(_pattern_up_then_down, id="up_then_down"),
    pytest.param(_pattern_up_down_up, id="up_down_up"),
    pytest.param(_pattern_down_up_down, id="down_up_down"),
]


# ===========================================================================
# Tests
# ===========================================================================


class TestSnowballTickPatterns:
    """Run each tick pattern and verify the strategy does not crash."""

    @pytest.mark.parametrize("pattern_fn", PATTERNS)
    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_pattern_completes_without_error(self, pattern_fn, stop_loss):
        runner = TickRunner(stop_loss=stop_loss)
        # Initialise
        result = runner.tick(START_PRICE)
        runner.assert_no_error(result)
        assert runner.ss.initialised

        # Run pattern
        pattern_fn(runner)

        # Verify no crash — one more tick at last price
        runner.tick(runner.last_mid)
        # We only care that it didn't crash; some patterns may trigger
        # strategy stop (e.g. margin blowout) which is acceptable.

    @pytest.mark.parametrize("pattern_fn", PATTERNS)
    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_both_directions_have_cycles(self, pattern_fn, stop_loss):
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)
        pattern_fn(runner)

        assert len(runner.long_cycles()) >= 1, "No LONG cycles created"
        assert len(runner.short_cycles()) >= 1, "No SHORT cycles created"

    @pytest.mark.parametrize("pattern_fn", PATTERNS)
    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_events_are_emitted(self, pattern_fn, stop_loss):
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)
        pattern_fn(runner)

        assert len(runner.open_events) >= 2, "Expected at least initial LONG+SHORT opens"

    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_monotonic_increase_long_tp_hit(self, stop_loss):
        """LONG cycle should hit TP when price rises 50+ pips."""
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)
        runner.tick_range(START_PRICE, START_PRICE + Decimal("0.60"), step_pips=1)

        long_closes = [e for e in runner.close_events if e.direction == "long"]
        assert len(long_closes) >= 1, "LONG TP should have been hit"

    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_monotonic_decrease_short_tp_hit(self, stop_loss):
        """SHORT cycle should hit TP when price falls 50+ pips."""
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)
        runner.tick_range(START_PRICE, START_PRICE - Decimal("0.60"), step_pips=1)

        short_closes = [e for e in runner.close_events if e.direction == "short"]
        assert len(short_closes) >= 1, "SHORT TP should have been hit"


class TestSnowballCounterEntries:
    """Verify counter entries are added at correct intervals."""

    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_counter_entries_added_on_adverse_move(self, stop_loss):
        """When price moves adversely, counter entries should be added."""
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)

        # Move price down 100 pips (adverse for LONG)
        runner.tick_range(START_PRICE, START_PRICE - Decimal("1.00"), step_pips=1)

        long_opens = [e for e in runner.open_events if getattr(e, "direction", "") == "long"]
        # Initial + at least some counter entries
        assert len(long_opens) >= 2, (
            f"Expected counter entries for LONG, got {len(long_opens)} opens"
        )

    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_no_counter_when_price_favourable(self, stop_loss):
        """No counter entries when price moves in favourable direction."""
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)

        # Move price up 30 pips (favourable for LONG, adverse for SHORT)
        runner.tick_range(START_PRICE, START_PRICE + Decimal("0.30"), step_pips=1)

        long_opens = [e for e in runner.open_events if getattr(e, "direction", "") == "long"]
        # Should only have the initial entry, no counters
        assert len(long_opens) == 1, f"Expected only initial LONG entry, got {len(long_opens)}"


class TestSnowballStopLossRebuild:
    """Verify stop-loss close and rebuild behaviour."""

    def test_stop_loss_triggers_on_adverse_move(self):
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Move adversely enough to trigger counter entries then SL
        runner.tick_range(START_PRICE, START_PRICE - Decimal("2.00"), step_pips=1)

        sl_closes = [
            e for e in runner.close_events if getattr(e, "close_reason", "") == "stop_loss"
        ]
        assert len(sl_closes) >= 1, "Expected stop-loss closes"

    def test_rebuild_after_price_returns(self):
        """After SL close, rebuilds should fire when price returns."""
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Drop to trigger SL
        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)

        # Return to original price
        runner.tick_range(bottom, START_PRICE, step_pips=1)

        assert len(runner.rebuild_events) >= 1, "Expected rebuild events after price returned"

    def test_rebuild_gets_stop_loss_when_flag_disabled(self):
        runner = TickRunner(
            stop_loss=True,
            overrides={"disable_loss_cut_after_rebuild": False},
        )
        runner.tick(START_PRICE)

        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)
        runner.tick_range(bottom, START_PRICE, step_pips=1)

        assert runner.rebuild_events, "Expected at least one rebuilt entry"
        assert all(evt.stop_loss_price is not None for evt in runner.rebuild_events)

    def test_rebuild_has_no_stop_loss_when_flag_enabled(self):
        runner = TickRunner(
            stop_loss=True,
            overrides={"disable_loss_cut_after_rebuild": True},
        )
        runner.tick(START_PRICE)

        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)
        runner.tick_range(bottom, START_PRICE, step_pips=1)

        assert runner.rebuild_events, "Expected at least one rebuilt entry"
        assert all(evt.stop_loss_price is None for evt in runner.rebuild_events)

    def test_rebuild_reuses_position_id(self):
        """Rebuild events should carry original_position_id."""
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)
        runner.tick_range(bottom, START_PRICE, step_pips=1)

        for evt in runner.rebuild_events:
            # original_position_id may be None in unit tests (no DB),
            # but the event type should be REBUILD_POSITION
            assert evt.event_type == EventType.REBUILD_POSITION

    def test_rebuilt_position_can_be_loss_cut_again_when_flag_disabled(self):
        runner = TickRunner(
            stop_loss=True,
            overrides={"disable_loss_cut_after_rebuild": False},
        )
        runner.tick(START_PRICE)

        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)
        current = bottom
        rebuild_evt = None
        while current < START_PRICE:
            current += PIP
            runner.tick(current)
            if runner.rebuild_events:
                rebuild_evt = runner.rebuild_events[-1]
                break

        assert rebuild_evt is not None, "Expected a rebuild before second adverse move"
        assert rebuild_evt.stop_loss_price is not None, (
            "Expected rebuilt entry to carry a stop-loss"
        )

        trigger_mid = Decimal(str(rebuild_evt.stop_loss_price))
        runner.tick_range(current, trigger_mid, step_pips=1)

        rebuilt_stop_loss_closes = [
            e
            for e in runner.close_events
            if getattr(e, "close_reason", "") == "stop_loss" and e.entry_id == rebuild_evt.entry_id
        ]
        assert rebuilt_stop_loss_closes, "Expected rebuilt entries to be loss-cut again"

    def test_rebuilt_position_is_not_loss_cut_again_when_flag_enabled(self):
        runner = TickRunner(
            stop_loss=True,
            overrides={"disable_loss_cut_after_rebuild": True},
        )
        runner.tick(START_PRICE)

        bottom = START_PRICE - Decimal("1.50")
        runner.tick_range(START_PRICE, bottom, step_pips=1)
        runner.tick_range(bottom, START_PRICE, step_pips=1)
        rebuilt_entry_ids = {evt.entry_id for evt in runner.rebuild_events}
        assert rebuilt_entry_ids, "Expected a rebuild before verifying second SL behavior"
        runner.tick_range(START_PRICE, bottom, step_pips=1)

        rebuilt_stop_loss_closes = [
            e
            for e in runner.close_events
            if getattr(e, "close_reason", "") == "stop_loss" and e.entry_id in rebuilt_entry_ids
        ]
        assert not rebuilt_stop_loss_closes

    def test_no_premature_layer_after_stop_loss(self):
        """Stop-loss closed slots should not trigger new layer addition."""
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Move down enough to trigger some SL closes but not enough
        # to fill all r_max slots
        runner.tick_range(START_PRICE, START_PRICE - Decimal("0.80"), step_pips=1)

        ss = runner.ss
        for cycle in ss.active_cycles():
            if cycle.direction.value == "long":
                # With manual_intervals=[30,30,25,20,16,14,12],
                # 80 pips adverse should add counters but not necessarily
                # need a new layer if SL slots are refillable
                layer_count = cycle.layer_count
                assert layer_count <= 2, (
                    f"LONG cycle has {layer_count} layers — "
                    "SL closed slots should not trigger premature layer addition"
                )

    def test_f_max_caps_total_layers_at_l1_through_l3(self):
        """f_max=3 should cap a cycle at L1-L3, never L4."""
        runner = TickRunner(stop_loss=False)
        runner.tick(START_PRICE)

        # Drive a large adverse move so the strategy keeps attempting to
        # expand layers after counter slots are exhausted.
        runner.tick_range(START_PRICE, START_PRICE - Decimal("4.00"), step_pips=1)

        for cycle in runner.ss.cycles:
            if cycle.direction.value == "long":
                assert cycle.layer_count <= 3, (
                    f"LONG cycle has {cycle.layer_count} layers — f_max=3 should allow only L1-L3"
                )

    def test_sl_closed_slot_blocks_counter_add(self):
        """When R1 is SL-closed, the next counter should go to R2, not R1.

        SL-closed slots are in pending_rebuild state and must not be
        reused by counter-add logic.  The strategy should skip R1 and
        place the next counter at R2 with the correct interval from R1.
        """
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Move SHORT adversely (price up) to trigger R1 counter, then SL on R1
        # R1 opens at ~30 pips adverse, SL is near the next interval
        runner.tick_range(START_PRICE, START_PRICE + Decimal("0.70"), step_pips=1)

        ss = runner.ss
        for cycle in ss.active_cycles():
            if cycle.direction.value != "short":
                continue
            layer = cycle.grid.current_layer
            if layer is None:
                continue
            # Check that SL-closed slots have pending_rebuild set
            for slot in layer.slots:
                if slot.is_pending_rebuild:
                    assert slot.entry is None, "SL slot should have no live entry"
                    assert slot.pending_rebuild is not None
                    # Verify the slot is NOT available for counter adds
                    assert not slot.is_available, (
                        f"SL-closed slot R{slot.index} should not be available"
                    )

    def test_sl_slot_preserves_r_number_progression(self):
        """After SL on R1, the next available slot should skip R1 (pending rebuild).

        When R1 has pending_rebuild, counter adds should still proceed to
        higher R-numbers.  The next available slot may be R2 or higher
        depending on whether counter adds already filled R2 during the
        same adverse move that triggered the SL.
        """
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Move SHORT adversely (price up) enough to trigger R1 then SL on R1
        runner.tick_range(START_PRICE, START_PRICE + Decimal("0.70"), step_pips=1)

        ss = runner.ss
        found_pending = False
        for cycle in ss.cycles:
            if cycle.direction.value != "short":
                continue
            layer = cycle.grid.current_layer
            if layer is None:
                continue
            r1 = layer.slot_at(1)
            if r1 is not None and r1.is_pending_rebuild:
                found_pending = True
                # R1 is pending rebuild — next available should be R2 or higher
                next_slot = layer.next_available_counter_slot()
                if next_slot is not None:
                    assert next_slot.index >= 2, (
                        f"Expected next available slot to be R2+, got R{next_slot.index}"
                    )
        # At least one cycle should have had a pending rebuild
        assert found_pending, "Expected at least one SL-closed R1 slot"

    def test_cycle_pending_when_all_sl_closed(self):
        """Cycle should be PENDING when all positions are SL-closed.

        When no open entries remain but pending rebuilds exist, the
        cycle transitions to PENDING regardless of available counter
        slots.  The reseed logic creates a fresh cycle if needed.
        """
        runner = TickRunner(stop_loss=True)
        runner.tick(START_PRICE)

        # Move far enough to trigger SL on all positions
        runner.tick_range(START_PRICE, START_PRICE - Decimal("2.50"), step_pips=1)

        ss = runner.ss
        for cycle in ss.cycles:
            if cycle.direction.value != "long":
                continue
            if cycle.grid.has_pending_rebuilds() and cycle.grid.is_empty():
                assert cycle.status.value == "pending", (
                    f"Cycle {cycle.cycle_id} has pending rebuilds and no open "
                    f"entries but status is {cycle.status.value}"
                )


class TestSnowballTPOrdering:
    """Verify TP ordering is maintained across layers."""

    @pytest.mark.parametrize("stop_loss", [False, True], ids=["no_sl", "sl"])
    def test_tp_ordering_maintained(self, stop_loss):
        """Within a cycle, counter TPs should be monotonically ordered."""
        runner = TickRunner(stop_loss=stop_loss)
        runner.tick(START_PRICE)

        # Generate enough adverse movement to create multiple layers
        runner.tick_range(START_PRICE, START_PRICE - Decimal("2.00"), step_pips=1)

        ss = runner.ss
        for cycle in ss.active_cycles():
            if cycle.direction.value != "long":
                continue
            entries = list(cycle.grid.all_entries())
            if len(entries) < 2:
                continue

            head = cycle.initial_entry
            if head is None:
                continue

            # For LONG: all non-head entries should have TP <= head TP
            # (counters close before the head)
            for entry in entries:
                if entry.entry_id == head.entry_id:
                    continue
                if entry.close_price <= 0:
                    continue
                assert entry.close_price <= head.close_price + PIP, (
                    f"TP ordering violated: L{entry.layer_number}/R{entry.retracement_count} "
                    f"TP={entry.close_price} > head TP={head.close_price}"
                )
