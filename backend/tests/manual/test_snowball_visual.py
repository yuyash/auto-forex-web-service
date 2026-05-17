#!/usr/bin/env python
"""Manual visual inspection test for Snowball strategy behaviour.

Run with:
    cd backend
    uv run python -m tests.manual.test_snowball_visual

Prints tick-by-tick strategy actions to stdout so a human can verify:
- Position opens/closes at correct prices and R-numbers
- Stop-loss triggers and pending_rebuild slot states
- Rebuild triggers when price returns
- Counter adds skip SL-closed slots
- Cycle completion / PENDING transitions

Scenarios:
1. Favourable move (price rises for LONG) → TP hit
2. Adverse move (price falls for LONG) → counter adds at correct intervals
3. Adverse move with SL → SL closes, then price returns → rebuilds
4. Double reversal → counters, SL, rebuild, then TP
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

# Django setup
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
django.setup()

from apps.trading.strategies.snowball.config import SnowballStrategyConfig  # noqa: E402
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState  # noqa: E402
from apps.trading.strategies.snowball.strategy import SnowballStrategy  # noqa: E402


# ---------------------------------------------------------------------------
# Config
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
    "m_th": "70",
    "m1_th": "50",
    "stop_loss_enabled": True,
    "emergency_enabled": True,
    "post_r_max_base_factor": "1",
    "refill_up_to": 3,
    "pip_size": "0.01",
    "reseed_on_all_pending": True,
}

SPREAD = Decimal("0.02")
PIP = Decimal("0.01")
START_PRICE = Decimal("155.000")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class DummyState:
    strategy_state: dict[str, Any] = field(default_factory=dict)
    current_balance: Decimal = Decimal("1000000")
    ticks_processed: int = 1


def _make_tick(ts: datetime, mid: Decimal) -> Any:
    from apps.trading.dataclasses.tick import Tick

    bid = mid - SPREAD / 2
    ask = mid + SPREAD / 2
    return Tick.create(instrument="USD_JPY", timestamp=ts, bid=bid, ask=ask, mid=mid)


class VisualRunner:
    """Run ticks and print every action to stdout."""

    def __init__(self, *, direction_filter: str | None = None) -> None:
        params = {**PROD_CONFIG}
        config = SnowballStrategyConfig.from_dict(params)
        self.strategy = SnowballStrategy("USD_JPY", PIP, config)
        self.state = DummyState()
        self.ts = datetime(2026, 1, 1, tzinfo=UTC)
        self.tick_count = 0
        self.direction_filter = direction_filter

    def tick(self, mid: Decimal, *, label: str = "") -> None:
        self.ts += timedelta(seconds=1)
        self.state.ticks_processed += 1
        self.tick_count += 1
        tick = _make_tick(self.ts, mid)
        result = self.strategy.on_tick(tick=tick, state=self.state)

        events = result.events
        if self.direction_filter:
            events = [e for e in events if getattr(e, "direction", "") == self.direction_filter]

        if events or label:
            bid = mid - SPREAD / 2
            ask = mid + SPREAD / 2
            tag = f" [{label}]" if label else ""
            print(f"\n--- Tick #{self.tick_count}: mid={mid} bid={bid} ask={ask}{tag} ---")
            for evt in events:
                etype = evt.event_type.value
                direction = getattr(evt, "direction", "?")
                desc = getattr(evt, "description", "")
                units = getattr(evt, "units", "")
                price = getattr(evt, "price", "")
                print(f"  {etype:20s} | {direction:5s} | units={units} | price={price}")
                if desc:
                    print(f"  {'':20s}   {desc}")

        if result.should_stop:
            print(f"\n  *** STRATEGY STOPPED: {result.stop_reason} ***")

    def tick_range(self, start: Decimal, end: Decimal, step_pips: int = 1) -> None:
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

    def print_grid(self, direction: str = "long") -> None:
        """Print the current grid state for a direction."""
        ss = SnowballStrategyState.from_strategy_state(self.state.strategy_state)
        print(f"\n{'=' * 70}")
        print(f"Grid state for {direction.upper()} cycles:")
        print(f"{'=' * 70}")
        for cycle in ss.cycles:
            if cycle.direction.value != direction:
                continue
            print(
                f"  Cycle #{cycle.cycle_id} | status={cycle.status.value} | "
                f"layers={cycle.layer_count}"
            )
            head = cycle.initial_entry
            head_id = head.entry_id if head else None
            for layer in cycle.grid.layers:
                print(f"    Layer L{layer.layer_number}:")
                for slot in layer.slots:
                    if slot.is_occupied:
                        e = slot.entry
                        assert e is not None
                        head_mark = " [HEAD]" if e.entry_id == head_id else ""
                        print(
                            f"      R{slot.index}: OCCUPIED | "
                            f"entry={e.entry_price} TP={e.close_price} "
                            f"SL={e.stop_loss_price} units={e.units}"
                            f"{head_mark}"
                        )
                    elif slot.is_pending_rebuild:
                        p = slot.pending_rebuild
                        assert p is not None
                        print(
                            f"      R{slot.index}: PENDING_REBUILD | "
                            f"entry={p.entry_price} TP={p.close_price} "
                            f"units={p.units}"
                        )
                    elif slot.ever_closed:
                        print(f"      R{slot.index}: SEALED")
                    else:
                        print(f"      R{slot.index}: EMPTY")
        print(f"{'=' * 70}")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def scenario_1_favourable_move():
    """Scenario 1: Price rises steadily → LONG TP hit."""
    print("\n" + "=" * 70)
    print("SCENARIO 1: Favourable move (LONG TP)")
    print("=" * 70)
    print("Price rises from 155.000 to 155.600 (+60 pips)")
    print("Expected: LONG initial entry, then TP at +50 pips, re-entry")

    runner = VisualRunner(direction_filter="long")
    runner.tick(START_PRICE, label="INIT")
    runner.tick_range(START_PRICE + PIP, START_PRICE + Decimal("0.60"), step_pips=5)
    runner.print_grid("long")


def scenario_2_adverse_move():
    """Scenario 2: Price falls → counter entries at correct intervals."""
    print("\n" + "=" * 70)
    print("SCENARIO 2: Adverse move (LONG counters)")
    print("=" * 70)
    print("Price falls from 155.000 to 154.000 (-100 pips)")
    print("Expected: R1 at -30 pips, R2 at -60 pips, R3 at -85 pips")

    runner = VisualRunner(direction_filter="long")
    runner.tick(START_PRICE, label="INIT")
    runner.tick_range(START_PRICE - PIP, START_PRICE - Decimal("1.00"), step_pips=1)
    runner.print_grid("long")


def scenario_3_adverse_with_sl_and_rebuild():
    """Scenario 3: Adverse move triggers SL, then price returns → rebuild."""
    print("\n" + "=" * 70)
    print("SCENARIO 3: Stop-loss and rebuild")
    print("=" * 70)
    print("Price falls 150 pips (triggers SL), then returns to start")
    print("Expected: counters → SL closes → pending_rebuild slots → rebuilds")

    runner = VisualRunner(direction_filter="long")
    runner.tick(START_PRICE, label="INIT")

    bottom = START_PRICE - Decimal("1.50")
    print(f"\n--- Phase 1: Drop to {bottom} ---")
    runner.tick_range(START_PRICE - PIP, bottom, step_pips=1)
    runner.print_grid("long")

    print(f"\n--- Phase 2: Return to {START_PRICE} ---")
    runner.tick_range(bottom + PIP, START_PRICE, step_pips=1)
    runner.print_grid("long")


def scenario_4_double_reversal():
    """Scenario 4: Drop, partial recovery, drop again, then full recovery."""
    print("\n" + "=" * 70)
    print("SCENARIO 4: Double reversal")
    print("=" * 70)
    print("Drop 80 pips → rise 50 pips → drop 80 pips → rise to start+60")
    print("Expected: counters, some TP, more counters/SL, rebuilds, final TP")

    runner = VisualRunner(direction_filter="long")
    runner.tick(START_PRICE, label="INIT")

    p1 = START_PRICE - Decimal("0.80")
    p2 = START_PRICE - Decimal("0.30")
    p3 = START_PRICE - Decimal("1.10")
    p4 = START_PRICE + Decimal("0.60")

    print(f"\n--- Phase 1: Drop to {p1} (-80 pips) ---")
    runner.tick_range(START_PRICE - PIP, p1, step_pips=1)
    runner.print_grid("long")

    print(f"\n--- Phase 2: Rise to {p2} (+50 pips from bottom) ---")
    runner.tick_range(p1 + PIP, p2, step_pips=1)
    runner.print_grid("long")

    print(f"\n--- Phase 3: Drop to {p3} (-80 pips from p2) ---")
    runner.tick_range(p2 - PIP, p3, step_pips=1)
    runner.print_grid("long")

    print(f"\n--- Phase 4: Rise to {p4} (full recovery + TP) ---")
    runner.tick_range(p3 + PIP, p4, step_pips=1)
    runner.print_grid("long")


def scenario_5_sl_slot_blocks_counter():
    """Scenario 5: Verify SL-closed slot blocks counter add."""
    print("\n" + "=" * 70)
    print("SCENARIO 5: SL-closed slot blocks counter add")
    print("=" * 70)
    print("SHORT cycle: price rises to trigger R1, then SL on R1")
    print("Expected: R1 SL → R1 becomes pending_rebuild → next counter is R2")

    runner = VisualRunner(direction_filter="short")
    runner.tick(START_PRICE, label="INIT")

    # Move price up to trigger SHORT R1 counter, then further to trigger SL
    runner.tick_range(START_PRICE + PIP, START_PRICE + Decimal("0.70"), step_pips=1)
    runner.print_grid("short")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    scenarios = [
        scenario_1_favourable_move,
        scenario_2_adverse_move,
        scenario_3_adverse_with_sl_and_rebuild,
        scenario_4_double_reversal,
        scenario_5_sl_slot_blocks_counter,
    ]

    if len(sys.argv) > 1:
        idx = int(sys.argv[1]) - 1
        if 0 <= idx < len(scenarios):
            scenarios[idx]()
        else:
            print(f"Invalid scenario number. Choose 1-{len(scenarios)}")
            sys.exit(1)
    else:
        for scenario in scenarios:
            scenario()

    print("\n\nDone.")


if __name__ == "__main__":
    main()
