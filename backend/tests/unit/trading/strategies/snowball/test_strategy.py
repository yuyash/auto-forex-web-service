"""Unit tests for SnowballStrategy class."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction, EventType, StrategyType
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    SnowballCycle,
    SnowballStrategyState,
    Slot,
    StopLossClosedEntry,
)
from apps.trading.strategies.snowball.pricing import (
    rebuild_take_profit_price,
    sync_weighted_average_counter_take_profits,
)
from apps.trading.strategies.snowball.reconciliation import reconcile_broker_positions
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
        assert result["rebuild_stop_loss_mode"] == "same"
        assert result["rebuild_take_profit_mode"] == "same"
        assert result["grid_order_validation_enabled"] is True
        assert result["preserve_highest_retracement_enabled"] is False
        assert result["stop_loss_mode"] == "auto"
        assert "preserve_highest_r_from" not in result

    def test_default_parameters(self):
        defaults = SnowballStrategy.default_parameters()
        assert isinstance(defaults, dict)
        assert "base_units" in defaults
        assert "m_pips" in defaults
        assert "disable_loss_cut_after_rebuild" in defaults
        assert "rebuild_stop_loss_mode" in defaults
        assert "rebuild_take_profit_mode" in defaults
        assert "grid_order_validation_enabled" in defaults
        assert "preserve_highest_retracement_enabled" in defaults
        assert defaults["stop_loss_mode"] == "auto"
        assert "preserve_highest_r_from" not in defaults

    def test_parse_config_accepts_persisted_default_parameters(self):
        cfg = SnowballStrategy.parse_config(
            SimpleNamespace(config_dict=SnowballStrategy.default_parameters())
        )

        assert cfg.preserve_highest_retracement_enabled is False
        assert cfg.preserve_highest_r_from == 0

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


class TestSnowballCycleTp:
    def test_rebuilt_r0_waits_for_adjusted_close_price(self):
        strategy = _strategy({"m_pips": "15"})
        state = SnowballStrategyState()
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 3, 1000, 2)
        rebuilt_r0 = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("141.774"),
            close_price=Decimal("143.391"),
            units=1500,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
            is_rebuild=True,
            lifecycle_realized_pnl=Decimal("-2425.5"),
            lifecycle_stop_loss_count=2,
        )
        layer.slot_at(0).fill(rebuilt_r0)
        cycle.add_layer(layer)
        state.cycles.append(cycle)

        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "141.954", "141.956")

        events = strategy._process_cycle_tp(state, tick, cycle)

        assert events == []
        assert layer.slot_at(0).entry is rebuilt_r0

    def test_rebuilt_r0_closes_at_adjusted_close_price(self):
        strategy = _strategy({"m_pips": "15"})
        state = SnowballStrategyState()
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 3, 1000, 2)
        rebuilt_r0 = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("141.774"),
            close_price=Decimal("143.391"),
            units=1500,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
            is_rebuild=True,
            lifecycle_realized_pnl=Decimal("-2425.5"),
            lifecycle_stop_loss_count=2,
        )
        layer.slot_at(0).fill(rebuilt_r0)
        cycle.add_layer(layer)
        state.cycles.append(cycle)

        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "143.391", "143.393")

        events = strategy._process_cycle_tp(state, tick, cycle)

        assert len(events) == 2
        assert events[0].event_type == EventType.CLOSE_POSITION
        assert events[0].exit_price == Decimal("143.391")

    def test_head_tp_waits_when_counter_target_is_not_hit(self):
        strategy = _strategy({"m_pips": "15"})
        state = SnowballStrategyState()
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 3, 1000, 2)
        rebuilt_r0 = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("141.774"),
            close_price=Decimal("143.391"),
            units=1500,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
            is_rebuild=True,
            lifecycle_realized_pnl=Decimal("-2425.5"),
            lifecycle_stop_loss_count=2,
        )
        counter = Entry(
            entry_id=2,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("141.500"),
            close_price=Decimal("143.500"),
            units=3000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
        )
        layer.slot_at(0).fill(rebuilt_r0)
        layer.slot_at(1).fill(counter)
        cycle.add_layer(layer)
        state.cycles.append(cycle)

        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "143.391", "143.393")

        events = strategy._process_cycle_tp(state, tick, cycle)

        assert events == []
        assert layer.slot_at(0).entry is rebuilt_r0
        assert layer.slot_at(1).entry is counter


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
                "preserve_highest_retracement_enabled": True,
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
                "preserve_highest_retracement_enabled": True,
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
                "preserve_highest_retracement_enabled": True,
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


class TestSnowballStopLossModes:
    def test_auto_mode_uses_interval_based_counter_stop_loss_formula(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "stop_loss_mode": "auto",
                "n_pips_head": "30",
            }
        )
        entry = Entry(
            entry_id=1,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("155.00"),
            close_price=Decimal("155.50"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
        )

        s._assign_configured_stop_loss(entry, 2)

        assert entry.stop_loss_price == Decimal("154.40")

    def test_constant_mode_uses_flat_pip_distance_from_slot_entry(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "stop_loss_mode": "constant",
                "stop_loss_pips_head": "30",
            }
        )
        entry = Entry(
            entry_id=1,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("155.00"),
            close_price=Decimal("155.50"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
        )

        s._assign_configured_stop_loss(entry, 2)

        assert entry.stop_loss_price == Decimal("154.70")

    def test_constant_mode_treats_stop_loss_pips_as_absolute_distance_for_short(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "stop_loss_mode": "constant",
                "stop_loss_pips_head": "30",
            }
        )
        entry = Entry(
            entry_id=1,
            step=2,
            direction=Direction.SHORT,
            entry_price=Decimal("155.00"),
            close_price=Decimal("154.50"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
        )

        s._assign_configured_stop_loss(entry, 2)

        assert entry.stop_loss_price == Decimal("155.30")


class TestSnowballRebuildStopLossModes:
    def _make_pending_rebuild(
        self,
        *,
        direction: Direction = Direction.LONG,
        stop_loss_price: str = "154.40",
        retracement_count: int = 1,
    ) -> StopLossClosedEntry:
        return StopLossClosedEntry(
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00") if direction == Direction.LONG else Decimal("154.40"),
            units=2000,
            direction=direction,
            role="counter",
            layer_number=1,
            retracement_count=retracement_count,
            step=2,
            cycle_id=1,
            stop_loss_price=Decimal(stop_loss_price),
        )

    def test_same_mode_reuses_original_stop_loss_price(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "disable_loss_cut_after_rebuild": False,
                "rebuild_stop_loss_mode": "same",
            }
        )
        entry = Entry(
            entry_id=9,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
            is_rebuild=True,
        )

        s._assign_rebuild_stop_loss(entry, self._make_pending_rebuild())

        assert entry.stop_loss_price == Decimal("154.40")

    def test_manual_mode_applies_absolute_pips_from_rebuild_entry(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "disable_loss_cut_after_rebuild": False,
                "rebuild_stop_loss_mode": "manual",
                "rebuild_stop_loss_manual_pips": ["8", "12", "16", "20", "24", "28", "32", "36"],
            }
        )
        entry = Entry(
            entry_id=9,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
            is_rebuild=True,
        )

        s._assign_rebuild_stop_loss(entry, self._make_pending_rebuild())

        assert entry.stop_loss_price == Decimal("154.58")


class TestSnowballRebuildTakeProfitModes:
    def _make_pending_rebuild(
        self,
        *,
        direction: Direction = Direction.LONG,
        retracement_count: int = 1,
        stop_loss_loss_pips: Decimal = Decimal("0"),
        close_price: Decimal | None = None,
    ) -> StopLossClosedEntry:
        return StopLossClosedEntry(
            entry_price=Decimal("154.70"),
            close_price=(
                close_price
                if close_price is not None
                else Decimal("155.00")
                if direction == Direction.LONG
                else Decimal("154.40")
            ),
            units=2000,
            direction=direction,
            role="counter",
            layer_number=1,
            retracement_count=retracement_count,
            step=2,
            cycle_id=1,
            stop_loss_loss_pips=stop_loss_loss_pips,
        )

    def test_same_mode_reuses_pending_take_profit_price(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_take_profit_mode": "same",
            }
        )

        tp = rebuild_take_profit_price(
            pending=self._make_pending_rebuild(),
            entry_price=Decimal("154.70"),
            pip_size=s.pip_size,
            config=s.config,
        )

        assert tp == Decimal("155.00")

    def test_manual_mode_applies_absolute_pips_from_rebuild_entry(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_take_profit_mode": "manual",
                "rebuild_take_profit_manual_pips": [
                    "8",
                    "12",
                    "16",
                    "20",
                    "24",
                    "28",
                    "32",
                    "36",
                ],
            }
        )

        long_tp = rebuild_take_profit_price(
            pending=self._make_pending_rebuild(direction=Direction.LONG),
            entry_price=Decimal("154.70"),
            pip_size=s.pip_size,
            config=s.config,
        )
        short_tp = rebuild_take_profit_price(
            pending=self._make_pending_rebuild(direction=Direction.SHORT),
            entry_price=Decimal("154.70"),
            pip_size=s.pip_size,
            config=s.config,
        )

        assert long_tp == Decimal("154.82")
        assert short_tp == Decimal("154.58")

    def test_recovery_mode_extends_same_take_profit_to_prior_loss_pips(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_take_profit_mode": "same",
                "rebuild_take_profit_recovery_enabled": True,
                "rebuild_take_profit_recovery_mode": "pips",
            }
        )

        short_tp = rebuild_take_profit_price(
            pending=self._make_pending_rebuild(
                direction=Direction.SHORT,
                stop_loss_loss_pips=Decimal("30.1"),
                close_price=Decimal("157.247"),
            ),
            entry_price=Decimal("157.397"),
            pip_size=Decimal("0.01"),
            config=s.config,
        )

        assert short_tp == Decimal("157.096")

    def test_recovery_mode_keeps_farther_existing_take_profit(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_take_profit_mode": "same",
                "rebuild_take_profit_recovery_enabled": True,
            }
        )

        long_tp = rebuild_take_profit_price(
            pending=self._make_pending_rebuild(
                direction=Direction.LONG,
                stop_loss_loss_pips=Decimal("10"),
            ),
            entry_price=Decimal("154.70"),
            pip_size=s.pip_size,
            config=s.config,
        )

        assert long_tp == Decimal("155.00")

    def test_manual_take_profit_mode_skips_grid_order_validation(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_take_profit_mode": "manual",
                "rebuild_take_profit_manual_pips": [
                    "8",
                    "12",
                    "16",
                    "20",
                    "24",
                    "28",
                    "32",
                    "36",
                ],
            }
        )
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer(
            layer_number=1,
            slots=[Slot(index=0), Slot(index=1)],
            base_units=1000,
            refill_up_to=2,
        )
        layer.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("155.00"),
                close_price=Decimal("155.50"),
                units=1000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="initial",
            )
        )
        layer.slot_at(1).fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.LONG,
                entry_price=Decimal("154.00"),
                close_price=Decimal("155.60"),
                units=2000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="counter",
                retracement_count=1,
            )
        )
        cycle.grid.layers.append(layer)

        s._validate_grid_ordering(cycle)

        assert s._grid_order_violation is None


class TestSnowballPricingHelpers:
    def test_weighted_average_sync_updates_all_counter_take_profits(self):
        layer = Layer.create(1, 3, 1000)
        layer.slot_at(0).fill(
            Entry(
                entry_id=1,
                step=1,
                direction=Direction.LONG,
                entry_price=Decimal("150.00"),
                close_price=Decimal("150.50"),
                units=1000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="initial",
            )
        )
        layer.slot_at(1).fill(
            Entry(
                entry_id=2,
                step=2,
                direction=Direction.LONG,
                entry_price=Decimal("149.70"),
                close_price=Decimal("150.00"),
                units=2000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="counter",
                retracement_count=1,
            )
        )
        layer.slot_at(2).fill(
            Entry(
                entry_id=3,
                step=3,
                direction=Direction.LONG,
                entry_price=Decimal("149.40"),
                close_price=Decimal("149.80"),
                units=3000,
                opened_at=datetime(2026, 1, 1, tzinfo=UTC),
                role="counter",
                retracement_count=2,
            )
        )

        close_price = sync_weighted_average_counter_take_profits(layer)

        assert close_price == Decimal("149.600")
        assert layer.slot_at(0).entry.close_price == Decimal("150.50")
        assert layer.slot_at(1).entry.close_price == Decimal("149.600")
        assert layer.slot_at(2).entry.close_price == Decimal("149.600")


class TestSnowballReconciliation:
    def test_reconcile_syncs_fill_price_and_dependent_prices(self):
        ss = SnowballStrategyState(initialised=True, account_nav=Decimal("100000"))
        cycle = SnowballCycle(cycle_id=1, direction=Direction.LONG)
        layer = Layer.create(1, 7, 1000)
        entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("150.00"),
            close_price=Decimal("150.50"),
            units=1000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="initial",
            layer_number=1,
            retracement_count=0,
            position_id="pos-1",
            stop_loss_price=Decimal("149.50"),
        )
        layer.slot_at(0).fill(entry)
        cycle.add_layer(layer)
        ss.cycles.append(cycle)
        state = DummyState(strategy_state=ss.to_dict())
        report = SimpleNamespace(
            removed_open_entries=0,
            relinked_open_entries=0,
            synthesized_open_entries=0,
            blockers=[],
        )
        position = SimpleNamespace(
            id="pos-1",
            direction="long",
            units=1000,
            entry_price=Decimal("150.02"),
            layer_index=1,
            retracement_count=0,
            entry_time=None,
            unrealized_pnl=Decimal("0"),
        )
        strategy_config = SimpleNamespace(
            config_dict=SnowballStrategyConfig.from_dict({"counter_tp_mode": "fixed"}).to_dict()
        )

        reconcile_broker_positions(
            state=state,
            open_positions=[position],
            report=report,
            strategy_config=strategy_config,
        )

        updated = SnowballStrategyState.from_strategy_state(state.strategy_state)
        updated_entry = updated.cycles[0].grid.layers[0].slot_at(0).entry
        assert updated_entry.entry_price == Decimal("150.02")
        assert updated_entry.close_price == Decimal("150.52")
        assert updated_entry.stop_loss_price == Decimal("149.52")


# ===================================================================
# Stop-loss rebuild toggle (rebuild_enabled / complete_cycle_when_empty)
# ===================================================================


class TestSnowballRebuildDisabled:
    """``rebuild_enabled=False`` closes SL slots permanently.

    The key invariant is: when a stop-loss fires under this mode, the
    slot is sealed (``slot.close(refillable=False)``), not converted
    into a ``pending_rebuild`` snapshot.  The cycle's
    ``_process_stop_loss_rebuilds`` pass returns no events.
    """

    def _make_cycle_with_two_entries(
        self,
    ) -> tuple[SnowballStrategyState, SnowballCycle, Entry, Entry]:
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
            stop_loss_price=Decimal("154.10"),
        )
        r1 = Entry(
            entry_id=2,
            step=2,
            direction=Direction.LONG,
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00"),
            units=2000,
            opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            role="counter",
            layer_number=1,
            retracement_count=1,
            stop_loss_price=Decimal("154.40"),
        )
        layer.slot_at(0).fill(r0)
        layer.slot_at(1).fill(r1)
        cycle.add_layer(layer)
        ss.cycles.append(cycle)
        return ss, cycle, r0, r1

    def test_stop_loss_seals_slot_without_pending_rebuild(self):
        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_enabled": False,
            }
        )
        ss, cycle, r0, r1 = self._make_cycle_with_two_entries()
        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "154.39", "154.41")

        events = s._process_stop_loss_closes(ss, tick, cycle)
        closed_ids = {event.entry_id for event in events}
        assert r1.entry_id in closed_ids

        layer = cycle.grid.layers[0]
        r1_slot = layer.slot_at(1)
        assert r1_slot is not None
        # Sealed: no live entry, no pending snapshot, no reopen allowed.
        assert r1_slot.entry is None
        assert r1_slot.pending_rebuild is None
        assert r1_slot.ever_closed is True
        # R0 is still alive.
        assert layer.slot_at(0).entry is r0

    def test_rebuild_pass_is_noop_when_disabled(self):
        """Even if a pending_rebuild somehow existed, the rebuild pass
        does nothing when the feature is off — no events, no state
        changes.  Guards against accidental re-enable by state
        deserialization of a persisted run.
        """
        from apps.trading.strategies.snowball.models import StopLossClosedEntry

        s = _strategy(
            {
                "stop_loss_enabled": True,
                "rebuild_enabled": False,
            }
        )
        ss, cycle, _r0, _r1 = self._make_cycle_with_two_entries()
        layer = cycle.grid.layers[0]
        r1_slot = layer.slot_at(1)
        assert r1_slot is not None
        # Manually install a pending snapshot to simulate stale state.
        r1_slot.entry = None
        r1_slot.pending_rebuild = StopLossClosedEntry(
            entry_price=Decimal("154.70"),
            close_price=Decimal("155.00"),
            units=2000,
            direction=Direction.LONG,
            role="counter",
            layer_number=1,
            retracement_count=1,
            step=2,
            cycle_id=1,
        )
        tick = _make_tick(datetime(2026, 1, 1, tzinfo=UTC), "154.71", "154.73")

        events = s._process_stop_loss_rebuilds(ss, tick, cycle)

        assert events == []
        assert r1_slot.entry is None
        assert r1_slot.pending_rebuild is not None


class TestSnowballCompleteCycleWhenEmpty:
    """``complete_cycle_when_empty`` gates automatic re-seed.

    Only relevant when ``rebuild_enabled=False``.  With the flag set,
    the strategy re-seeds a fresh cycle as soon as the last live entry
    of the direction closes; without it, the strategy stays idle for
    that direction.
    """

    def test_config_validation_requires_stop_loss_enabled(self):
        with pytest.raises(
            ValueError, match="complete_cycle_when_empty requires stop_loss_enabled"
        ):
            SnowballStrategyConfig.from_dict(
                {
                    "stop_loss_enabled": False,
                    "rebuild_enabled": False,
                    "complete_cycle_when_empty": True,
                }
            ).validate()

    def test_config_validation_requires_rebuild_disabled(self):
        with pytest.raises(
            ValueError, match="complete_cycle_when_empty requires rebuild_enabled to be false"
        ):
            SnowballStrategyConfig.from_dict(
                {
                    "stop_loss_enabled": True,
                    "rebuild_enabled": True,
                    "complete_cycle_when_empty": True,
                }
            ).validate()

    def test_defaults_rebuild_true_complete_cycle_false(self):
        cfg = SnowballStrategyConfig.from_dict({})
        assert cfg.rebuild_enabled is True
        assert cfg.complete_cycle_when_empty is False


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
