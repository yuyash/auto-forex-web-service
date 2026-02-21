"""Comprehensive unit tests for FloorStrategy tick-driven behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import EventType
from apps.trading.events import (
    AddLayerEvent,
    GenericStrategyEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    TakeProfitEvent,
    VolatilityLockEvent,
)
from apps.trading.strategies.floor.models import FloorStrategyConfig
from apps.trading.strategies.floor.strategy import FloorStrategy


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


def _strategy(config_updates: dict[str, Any] | None = None) -> FloorStrategy:
    params: dict[str, Any] = {
        "base_lot_size": 1,
        "retracement_lot_mode": "additive",
        "retracement_lot_amount": 1,
        "retracement_pips": 5,
        "take_profit_pips": 5,
        "max_layers": 3,
        "max_retracements_per_layer": 2,
        "lot_unit_size": 1000,
        "margin_rate": "0.04",
        "margin_cut_start_ratio": "1000",  # disabled by default in tests
        "margin_cut_target_ratio": "500",
        "volatility_lock_multiplier": "999",
        "volatility_unlock_multiplier": "1.5",
        "market_condition_override_enabled": False,
        "dynamic_parameter_adjustment_enabled": False,
    }
    if config_updates:
        params.update(config_updates)
    config = FloorStrategyConfig.from_dict(params)
    return FloorStrategy("USD_JPY", Decimal("0.01"), config)


def _first_event(result):
    assert result.events, "Expected at least one event"
    return result.events[0]


class TestFloorStrategyOnTick:
    """Tick scenario tests for strategy logic."""

    def test_initial_entry_is_created(self) -> None:
        strategy = _strategy()
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        result = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)

        event = _first_event(result)
        assert isinstance(event, InitialEntryEvent)
        assert event.event_type == EventType.INITIAL_ENTRY
        assert state.strategy_state["open_entries"]

    def test_retracement_entry_on_adverse_move(self) -> None:
        strategy = _strategy()
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        _ = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "149.85", "149.87"),
            state=state,
        )

        assert any(isinstance(ev, RetracementEvent) for ev in result.events)
        assert len(state.strategy_state["open_entries"]) >= 2

    def test_take_profit_closes_latest_entry_first(self) -> None:
        strategy = _strategy()
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        _ = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        _ = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "149.85", "149.87"),
            state=state,
        )
        entry_ids_before = [item["entry_id"] for item in state.strategy_state["open_entries"]]
        latest_id = max(entry_ids_before)

        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=120), "150.30", "150.32"),
            state=state,
        )

        take_profit_events = [ev for ev in result.events if isinstance(ev, TakeProfitEvent)]
        assert take_profit_events
        remaining_ids = [item["entry_id"] for item in state.strategy_state["open_entries"]]
        assert latest_id not in remaining_ids

    def test_moves_to_new_floor_when_retracements_exceeded(self) -> None:
        strategy = _strategy(
            {
                "max_retracements_per_layer": 0,
                "max_layers": 2,
                "retracement_pips": 5,
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        _ = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "149.80", "149.82"),
            state=state,
        )

        assert any(isinstance(ev, AddLayerEvent) for ev in result.events)
        assert state.strategy_state["active_floor_index"] == 1

    def test_returns_to_previous_floor_using_return_stack(self) -> None:
        strategy = _strategy(
            {
                "max_retracements_per_layer": 0,
                "max_layers": 3,
                "retracement_pips": 5,
                "floor_profiles": [
                    {"take_profit_pips": 4, "retracement_pips": 5},
                    {"take_profit_pips": 4, "retracement_pips": 5},
                    {"take_profit_pips": 4, "retracement_pips": 5},
                ],
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        strategy._choose_direction = lambda _state: "long"  # type: ignore[method-assign]

        _ = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        _ = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "149.80", "149.82"),
            state=state,
        )  # floor 1
        state.ticks_processed += 1
        _ = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=120), "149.60", "149.62"),
            state=state,
        )  # floor 2
        assert state.strategy_state["active_floor_index"] == 2

        # Favorable move to TP floor 2; should return to floor 1 (stack pop), not home floor 0.
        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=180), "150.20", "150.22"),
            state=state,
        )
        assert any(isinstance(ev, RemoveLayerEvent) for ev in result.events)
        assert state.strategy_state["active_floor_index"] == 1

    def test_per_floor_take_profit_and_retracement_are_used(self) -> None:
        strategy = _strategy(
            {
                "max_retracements_per_layer": 0,
                "max_layers": 2,
                "floor_profiles": [
                    {"take_profit_pips": 3, "retracement_pips": 5},
                    {"take_profit_pips": 11, "retracement_pips": 20},
                ],
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        _ = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)
        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "149.80", "149.82"),
            state=state,
        )

        floor1_entries = [
            item for item in state.strategy_state["open_entries"] if int(item["floor_index"]) == 1
        ]
        assert floor1_entries
        # floor profile for floor 1 should be applied to initial entry.
        assert Decimal(str(floor1_entries[-1]["take_profit_pips"])) == Decimal("11")

        # 8 pips favorable should NOT close floor 1 position because TP is 11 pips.
        state.ticks_processed += 1
        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=120), "149.90", "149.92"),
            state=state,
        )
        assert not any(isinstance(ev, TakeProfitEvent) for ev in result.events)

    def test_volatility_lock_and_unlock(self) -> None:
        strategy = _strategy(
            {
                "volatility_lock_multiplier": 1.2,
                "volatility_unlock_multiplier": 0.8,
                "atr_period": 3,
                "atr_baseline_period": 5,
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        strategy._choose_direction = lambda _state: "long"  # type: ignore[method-assign]
        current_atr = Decimal("5")
        baseline_atr = Decimal("10")

        def _atr_stub(_floor_state, period):
            if period == strategy.config.atr_period:
                return current_atr
            return baseline_atr

        strategy._estimate_atr_pips = _atr_stub  # type: ignore[method-assign]

        prices = [("150.00", "150.02"), ("149.50", "149.52"), ("149.55", "149.57")]

        lock_seen = False
        unlock_seen = False
        for idx, (bid, ask) in enumerate(prices):
            if idx == 1:
                current_atr = Decimal("20")  # lock (20 >= 10 * 1.2)
            if idx == 2:
                current_atr = Decimal("6")  # unlock (6 <= 10 * 0.8)
            state.ticks_processed = idx + 1
            result = strategy.on_tick(
                tick=_make_tick(ts + timedelta(seconds=60 * idx), bid, ask),
                state=state,
            )
            if any(isinstance(ev, VolatilityLockEvent) for ev in result.events):
                lock_seen = True
            if any(
                isinstance(ev, GenericStrategyEvent)
                and ev.event_type == EventType.STATUS_CHANGED
                and ev.data.get("kind") == "volatility_unlock"
                for ev in result.events
            ):
                unlock_seen = True

        assert lock_seen
        assert unlock_seen

    def test_margin_protection_emits_units_and_reduces_entries_partially(self) -> None:
        strategy = _strategy(
            {
                "margin_cut_start_ratio": "0.6",
                "margin_cut_target_ratio": "0.5",
                "margin_rate": "0.04",
            }
        )
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        state = DummyState(
            strategy_state={
                "open_entries": [
                    {
                        "entry_id": 1,
                        "floor_index": 0,
                        "direction": "long",
                        "entry_price": "149.00",
                        "units": 1000,
                        "take_profit_pips": "20",
                        "opened_at": ts.isoformat(),
                        "is_initial": True,
                    },
                    {
                        "entry_id": 2,
                        "floor_index": 0,
                        "direction": "long",
                        "entry_price": "148.50",
                        "units": 1500,
                        "take_profit_pips": "20",
                        "opened_at": (ts + timedelta(seconds=60)).isoformat(),
                        "is_initial": False,
                    },
                ],
                "floor_retracement_counts": {"0": 1},
            },
            current_balance=Decimal("1000"),
            ticks_processed=2,
        )

        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=120), "100.00", "100.02"),
            state=state,
        )

        margin_events = [ev for ev in result.events if isinstance(ev, MarginProtectionEvent)]
        assert margin_events
        event = margin_events[0]
        assert event.units_to_close is not None
        assert event.units_to_close > 0
        # With deeply negative NAV (balance=1000, unrealized ~ -121k), all
        # entries are closed.  The strategy bails out early after margin
        # protection (no new initial entry on the same tick).
        remaining_units = sum(int(item["units"]) for item in state.strategy_state["open_entries"])
        assert remaining_units < 2500

    def test_margin_protection_can_be_disabled(self) -> None:
        strategy = _strategy(
            {
                "margin_protection_enabled": False,
                "margin_cut_start_ratio": "0.0",  # would always trigger if enabled
                "margin_cut_target_ratio": "0.0",
                "margin_rate": "0.04",
            }
        )
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        state = DummyState(
            strategy_state={
                "open_entries": [
                    {
                        "entry_id": 1,
                        "floor_index": 0,
                        "direction": "long",
                        "entry_price": "149.00",
                        "units": 1000,
                        "take_profit_pips": "20",
                        "opened_at": ts.isoformat(),
                        "is_initial": True,
                    }
                ],
            },
            current_balance=Decimal("1000"),
            ticks_processed=2,
        )

        result = strategy.on_tick(
            tick=_make_tick(ts + timedelta(seconds=60), "100.00", "100.02"),
            state=state,
        )

        assert not any(isinstance(ev, MarginProtectionEvent) for ev in result.events)
        entry1 = next(
            (item for item in state.strategy_state["open_entries"] if int(item["entry_id"]) == 1),
            None,
        )
        assert entry1 is not None
        assert int(entry1["units"]) == 1000

    def test_volatility_check_can_be_disabled(self) -> None:
        strategy = _strategy(
            {
                "volatility_check_enabled": False,
                "volatility_lock_multiplier": 1.2,
                "volatility_unlock_multiplier": 0.8,
                "atr_period": 3,
                "atr_baseline_period": 5,
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        strategy._choose_direction = lambda _state: "long"  # type: ignore[method-assign]
        strategy._estimate_atr_pips = lambda *_args, **_kwargs: Decimal("999")  # type: ignore[method-assign]

        result = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.02"), state=state)

        assert not any(isinstance(ev, VolatilityLockEvent) for ev in result.events)
        assert state.strategy_state.get("volatility_locked") is not True

    def test_market_condition_override_skips_entries(self) -> None:
        strategy = _strategy(
            {
                "market_condition_override_enabled": True,
                "market_condition_spread_limit_pips": 1.0,
            }
        )
        state = DummyState()
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        # spread = 3 pips (0.03 / 0.01)
        result = strategy.on_tick(tick=_make_tick(ts, "150.00", "150.03"), state=state)

        assert any(
            isinstance(ev, GenericStrategyEvent) and ev.data.get("kind") == "entry_skipped"
            for ev in result.events
        )
        assert not state.strategy_state.get("open_entries")
