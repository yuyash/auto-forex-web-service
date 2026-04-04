"""Trading engine for Snowball strategy.

Implements a cycle-based hedging strategy:
- Each cycle starts with an initial entry and tracks its own counter entries
- Hedging mode: LONG and SHORT cycles run independently in parallel
- Non-hedging mode: a single LONG cycle
- Multi-level margin protection (shrink → lock → emergency)
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from apps.trading.dataclasses import EventExecutionResult, StrategyResult
from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction, EventType, StrategyType
from apps.trading.events import (
    ClosePositionEvent,
    GenericStrategyEvent,
    StrategyEvent,
)
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.registry import register_strategy
from apps.trading.strategies.snowball.calculators import (
    counter_interval_pips,
    counter_tp_pips,
)
from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
)
from apps.trading.utils import quote_to_account_rate

logger: Logger = getLogger(__name__)


@register_strategy(
    id="snowball",
    schema="trading/schemas/snowball.json",
    display_name="Snowball Strategy",
    description=(
        "Cycle-based hedging strategy: rotational profit-taking on initial entries "
        "and averaging-down with step-based partial closes on counter entries."
    ),
)
class SnowballStrategy(Strategy):
    """Main trading engine for Snowball strategy."""

    config: SnowballStrategyConfig

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        config: SnowballStrategyConfig,
    ) -> None:
        super().__init__(instrument, pip_size, config)
        self._hedging_enabled: bool = True
        self._close_order_violation: str | None = None
        logger.info(
            "Initialised Snowball engine: instrument=%s, pip_size=%s",
            instrument,
            pip_size,
        )

    # ------------------------------------------------------------------
    # Registry interface
    # ------------------------------------------------------------------

    @staticmethod
    def parse_config(strategy_config: Any) -> SnowballStrategyConfig:
        return SnowballStrategyConfig.from_dict(strategy_config.config_dict)

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        return SnowballStrategyConfig.from_dict(dict(parameters)).to_dict()

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        return SnowballStrategyConfig.from_dict({}).to_dict()

    @classmethod
    def validate_parameters(
        cls,
        *,
        parameters: dict[str, Any],
        config_schema: dict[str, Any] | None = None,
    ) -> None:
        super().validate_parameters(parameters=parameters, config_schema=config_schema)
        cfg = SnowballStrategyConfig.from_dict(parameters)
        cfg.validate()

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.SNOWBALL

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _margin_ratio(self, state: ExecutionState, ss: SnowballStrategyState) -> Decimal:
        nav = ss.account_nav
        if nav <= 0:
            return Decimal("0")
        all_entries = ss.all_entries()
        if not all_entries:
            return Decimal("0")
        long_units = sum(abs(e.units) for e in all_entries if e.is_long)
        short_units = sum(abs(e.units) for e in all_entries if e.is_short)
        total_units = max(long_units, short_units)
        if total_units == 0:
            return Decimal("0")
        mid = ss.last_mid or Decimal("0")
        if mid <= 0:
            return Decimal("0")
        conv = quote_to_account_rate(self.instrument, mid, self.account_currency)
        margin_rate = Decimal("0.04")
        required = mid * Decimal(str(total_units)) * margin_rate * conv
        return (required / nav) * Decimal("100")

    # ------------------------------------------------------------------
    # Entry helpers
    # ------------------------------------------------------------------

    def _close_entry(
        self,
        tick: Tick,
        entry: Entry,
        *,
        description: str = "",
        close_reason: str = "",
        actual_tp_pips: Decimal | None = None,
        validation_status: str = "",
    ) -> ClosePositionEvent:
        """Create a ClosePositionEvent from an Entry."""
        return entry.to_close_event(
            tick,
            instrument=self.instrument,
            pip_size=self.pip_size,
            account_currency=self.account_currency,
            description=description,
            close_reason=close_reason,
            actual_tp_pips=actual_tp_pips,
            validation_status=validation_status,
        )

    # ------------------------------------------------------------------
    # Cycle lifecycle
    # ------------------------------------------------------------------

    def _create_cycle(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        direction: Direction,
    ) -> tuple[list[StrategyEvent], SnowballCycle]:
        """Create a new cycle with an initial entry. Returns (events, cycle)."""
        cfg = self.config
        units = cfg.trend_lot_size * cfg.base_units
        price = tick.ask if direction == Direction.LONG else tick.bid
        if direction == Direction.LONG:
            close_price = price + cfg.m_pips * self.pip_size
            formula = f"{price} + {cfg.m_pips} * {self.pip_size}"
        else:
            close_price = price - cfg.m_pips * self.pip_size
            formula = f"{price} - {cfg.m_pips} * {self.pip_size}"

        entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=units,
            step=1,
            close_price=close_price,
            role="initial",
        )
        entry.expected_tp_pips = cfg.m_pips
        entry.validation_status = "pass"
        evt = entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Initial entry ({direction.value.upper()}) | units={units}, TP={close_price:.3f}"
            ),
        )
        cycle = SnowballCycle(
            cycle_id=entry.entry_id,
            direction=direction,
            initial_entry=entry,
        )
        # Create the first layer (L1) with r_max empty slots
        layer1 = Layer.create(1, cfg.r_max, cfg.base_units, cfg.refill_up_to)
        cycle.add_layer(layer1)
        ss.cycles.append(cycle)
        return [evt], cycle

    def _close_and_reenter(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Close the initial entry (TP hit), mark cycle completed, create new cycle."""
        entry = cycle.initial_entry
        if entry is None:
            return []
        direction = cycle.direction
        exit_price = entry.exit_price(tick)
        pips_gained = abs(exit_price - entry.entry_price) / self.pip_size

        events: list[StrategyEvent] = []

        logger.info(
            "TP hit (%s): entry=%s, exit=%s, +%.1f pips, units=%s",
            direction.value.upper(),
            entry.entry_price,
            exit_price,
            pips_gained,
            entry.units,
        )
        events.append(
            self._close_entry(
                tick,
                entry,
                description=(
                    f"TP ({direction.value.upper()}) | entry={entry.entry_price:.3f}, "
                    f"exit={exit_price:.3f}, +{pips_gained:.1f} pips"
                ),
                close_reason="tp",
                actual_tp_pips=pips_gained,
                validation_status="pass",
            )
        )
        cycle.completed = True

        # Re-entry: new cycle in the same direction
        new_events, _new_cycle = self._create_cycle(ss, tick, direction)
        logger.info(
            "Re-entry (%s) after TP: new cycle_id=%d",
            direction.value.upper(),
            _new_cycle.cycle_id,
        )
        events.extend(new_events)
        return events

    def _fail_close_order_violation(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Build a stop event when a close-order violation is detected.

        This sets ``should_stop`` on the next StrategyResult so the executor
        marks the task as FAILED instead of silently continuing.
        """
        open_entries = []
        for layer in cycle.layers:
            for e in layer.all_entries():
                open_entries.append(
                    f"L{e.layer_number}/R{e.retracement_count} "
                    f"entry={e.entry_price:.3f} tp={e.close_price:.3f}"
                )
        initial = cycle.initial_entry
        initial_price = f"{initial.entry_price:.3f}" if initial else "None"
        initial_tp = f"{initial.close_price:.3f}" if initial else "None"
        detail = (
            f"cycle_id={cycle.cycle_id}, direction={cycle.direction.value}, "
            f"initial_entry={initial_price}, "
            f"initial_tp={initial_tp}, "
            f"open_counters=[{', '.join(open_entries)}], "
            f"tick_bid={tick.bid}, tick_ask={tick.ask}"
        )
        logger.error("Close order violation detail: %s", detail)
        # Store the violation so on_tick returns should_stop=True
        self._close_order_violation = detail
        return []

    # ------------------------------------------------------------------
    # Per-cycle tick processing
    # ------------------------------------------------------------------

    def _process_cycle_tp(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Check if the initial entry hit its TP target.

        The initial entry (L1/R0) must only close when no counter entries
        remain open.  If counter entries are still present, their TPs should
        be reached first (they are closer to the current price).  Closing
        L1/R0 while counters are open is a close-order violation.
        """
        if cycle.completed:
            return []
        entry = cycle.initial_entry
        if not entry:
            return []
        direction = cycle.direction
        m_dyn = self.config.m_pips

        hit = False
        if direction == Direction.LONG and tick.bid >= entry.entry_price + m_dyn * self.pip_size:
            hit = True
        elif direction == Direction.SHORT and tick.ask <= entry.entry_price - m_dyn * self.pip_size:
            hit = True

        if not hit:
            return []

        # Guard: do not close L1/R0 while counter entries are still open.
        # Counter TPs should be reached before the initial entry TP.
        has_open_counters = any(layer.has_open_entries() for layer in cycle.layers)
        if has_open_counters:
            logger.error(
                "CLOSE ORDER VIOLATION: L1/R0 TP reached while counter entries "
                "are still open — cycle_id=%d, direction=%s. "
                "Failing task to prevent data corruption.",
                cycle.cycle_id,
                direction.value,
            )
            return self._fail_close_order_violation(ss, tick, cycle)

        return self._close_and_reenter(ss, tick, cycle)

    def _process_cycle_counter_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Close slot entries from highest R in newest layer, one per tick.

        Close order: newest layer highest R → ... → R1 → layer initial →
        previous layer highest R → ... → L1/R0 (cycle end).
        """
        if cycle.completed:
            return []

        # Walk layers from newest to oldest — close highest occupied slot
        for layer in reversed(cycle.layers):
            highest = layer.highest_occupied_slot()
            if highest is None or highest.entry is None:
                continue

            entry = highest.entry
            if entry.close_price <= 0:
                continue

            hit = False
            if entry.is_long and tick.bid >= entry.close_price:
                hit = True
            elif entry.is_short and tick.ask <= entry.close_price:
                hit = True
            if not hit:
                continue

            exit_price = entry.exit_price(tick)
            pips_gained = abs(exit_price - entry.entry_price) / self.pip_size

            logger.info(
                "Counter TP (%s): L%s/R%s, +%.1f pips",
                entry.direction.value.upper(),
                entry.layer_number,
                entry.retracement_count,
                pips_gained,
            )
            layer.close_slot(highest.index)
            cycle.counter_close_count += 1

            return [
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"Counter TP ({entry.direction.value.upper()}) | "
                        f"L{entry.layer_number}/R{entry.retracement_count}, "
                        f"entry={entry.entry_price:.3f}, "
                        f"exit={exit_price:.3f}, +{pips_gained:.1f} pips"
                    ),
                    close_reason="counter_tp",
                    actual_tp_pips=pips_gained,
                    validation_status="pass",
                )
            ]

        # Close layer-initial entries (L2+) when all slots are empty
        for layer in reversed(cycle.layers):
            if layer.layer_number == 1:
                continue
            if layer.initial_entry is None:
                continue
            if layer.occupied_slots():
                break  # still has slot entries

            entry = layer.initial_entry
            if entry.close_price <= 0:
                continue

            hit = False
            if entry.is_long and tick.bid >= entry.close_price:
                hit = True
            elif entry.is_short and tick.ask <= entry.close_price:
                hit = True
            if not hit:
                continue

            exit_price = entry.exit_price(tick)
            pips_gained = abs(exit_price - entry.entry_price) / self.pip_size

            logger.info(
                "Layer initial TP (%s): L%s, +%.1f pips — removing layer",
                entry.direction.value.upper(),
                layer.layer_number,
                pips_gained,
            )
            # Remove the layer entirely so current_layer reverts to the
            # previous one.  L2 will only be recreated when the previous
            # layer's slots get sealed again (needs_new_layer).
            cycle.layers.remove(layer)

            return [
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"Layer initial TP ({entry.direction.value.upper()}) | "
                        f"L{layer.layer_number}, entry={entry.entry_price:.3f}, "
                        f"exit={exit_price:.3f}, +{pips_gained:.1f} pips"
                    ),
                    close_reason="layer_initial_tp",
                    actual_tp_pips=pips_gained,
                    validation_status="pass",
                )
            ]

        return []

    def _process_cycle_counter_adds(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Add a new counter entry if adverse distance threshold is met."""
        if cycle.completed:
            return []
        cfg = self.config
        layer = cycle.current_layer
        if layer is None:
            return []

        # Need a new layer?
        if layer.needs_new_layer:
            if cycle.layer_count >= cfg.f_max:
                return []

            # Gate: cycle initial entry must be losing
            initial = cycle.initial_entry
            if not initial:
                return []
            if initial.unrealised_loss_pips(tick.mid, self.pip_size) <= 0:
                return []

            # Gate: price must have moved adversely from the highest
            # occupied slot in the current layer (same check as normal
            # counter adds).  Without this, a new layer would be created
            # immediately after a sealed slot is detected, regardless of
            # price movement.
            direction = cycle.direction
            highest = layer.highest_occupied_slot()
            if highest is not None and highest.entry is not None:
                ref_price = highest.entry.entry_price
                if direction == Direction.LONG:
                    adverse = (ref_price - tick.mid) / self.pip_size
                else:
                    adverse = (tick.mid - ref_price) / self.pip_size
                interval = counter_interval_pips(highest.index + 1, cfg)
                if adverse < interval:
                    return []

            return self._open_layer_initial(ss, tick, cycle)

        # Find the next available slot
        slot = layer.next_available_slot()
        if slot is None:
            return []

        # Gate: cycle initial entry must be losing
        initial = cycle.initial_entry
        if not initial:
            return []
        if initial.unrealised_loss_pips(tick.mid, self.pip_size) <= 0:
            return []

        # Measure adverse distance from the appropriate reference
        direction = cycle.direction
        occupied = layer.occupied_slots()
        if occupied:
            latest_entry = max(occupied, key=lambda s: s.index).entry
            assert latest_entry is not None
            if direction == Direction.LONG:
                adverse = (latest_entry.entry_price - tick.mid) / self.pip_size
            else:
                adverse = (tick.mid - latest_entry.entry_price) / self.pip_size
        else:
            reference = layer.initial_entry if layer.initial_entry is not None else initial
            adverse = reference.unrealised_loss_pips(tick.mid, self.pip_size)

        interval = counter_interval_pips(slot.index, cfg)
        if adverse < interval:
            return []

        # Build the entry
        units = (slot.index + 1) * layer.base_units
        new_price = tick.ask if direction == Direction.LONG else tick.bid
        layer_ref = layer.initial_entry if layer.layer_number > 1 else initial

        if cfg.counter_tp_mode == "weighted_avg":
            close_price, formula = layer.weighted_avg_close_price(
                new_price, units, include_initial=layer_ref
            )
        else:
            tp = counter_tp_pips(slot.index, cfg)
            if direction == Direction.LONG:
                close_price = new_price + tp * self.pip_size
            else:
                close_price = new_price - tp * self.pip_size
            op = "+" if direction == Direction.LONG else "-"
            formula = f"{new_price} {op} {tp} * {self.pip_size}"

        entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=units,
            step=slot.index + 1,
            close_price=close_price,
            role="counter",
            layer_number=layer.layer_number,
            retracement_count=slot.index,
            root_entry_id=initial.entry_id,
            parent_entry_id=initial.entry_id,
        )
        entry.expected_interval_pips = interval
        entry.actual_interval_pips = adverse
        entry.validation_status = "pass"

        logger.info(
            "Counter add (%s) in cycle %d: L%d/R%d, units=%d, adverse=%.1f pips",
            direction.value.upper(),
            cycle.cycle_id,
            layer.layer_number,
            slot.index,
            units,
            adverse,
        )

        evt = entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Counter add ({direction.value.upper()}) | "
                f"L{layer.layer_number}/R{slot.index}, units={units}, "
                f"adverse={adverse:.1f} pips, TP={close_price:.3f}"
            ),
        )
        slot.fill(entry)

        # Update close prices for non-weighted_avg modes
        if cfg.counter_tp_mode != "weighted_avg":
            for s in layer.slots:
                if s.entry is None or s.entry.is_hedge:
                    continue
                step_tp = counter_tp_pips(s.index, cfg)
                if direction == Direction.LONG:
                    s.entry.close_price = s.entry.entry_price + step_tp * self.pip_size
                else:
                    s.entry.close_price = s.entry.entry_price - step_tp * self.pip_size

        return [evt]

    def _open_layer_initial(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Open a layer-initial entry for a new layer."""
        cfg = self.config
        initial = cycle.initial_entry
        if initial is None:
            return []

        # Gate: don't build layer initial if cycle initial is not losing
        if initial.unrealised_loss_pips(tick.mid, self.pip_size) <= 0:
            return []

        direction = cycle.direction

        # Creating a brand new layer
        prev_layer = cycle.current_layer
        assert prev_layer is not None
        prev_layer_num = prev_layer.layer_number
        new_layer_number = prev_layer_num + 1
        new_base_units = int(Decimal(str(cfg.base_units)) * cfg.post_r_max_base_factor)
        layer = Layer.create(new_layer_number, cfg.r_max, new_base_units, cfg.refill_up_to)
        cycle.add_layer(layer)

        price = tick.ask if direction == Direction.LONG else tick.bid
        layer_entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=cfg.trend_lot_size * layer.base_units,
            step=1,
            close_price=Decimal("0"),
            role="layer_initial",
            layer_number=layer.layer_number,
            retracement_count=0,
            root_entry_id=initial.entry_id,
            parent_entry_id=initial.entry_id,
        )

        # Compute close price from previous layer's highest slot close price
        prev_layer_obj = cycle.find_layer(prev_layer_num)
        prev_initial = cycle.initial_for_layer(prev_layer_num)
        if prev_layer_obj is not None:
            close_price, formula = layer.layer_initial_close_price(
                price,
                abs(layer_entry.units),
                prev_layer_obj,
                prev_initial,
                direction=direction,
                pip_size=self.pip_size,
                m_pips=cfg.m_pips,
            )
        else:
            # Fallback: use m_pips
            if direction == Direction.LONG:
                close_price = price + cfg.m_pips * self.pip_size
            else:
                close_price = price - cfg.m_pips * self.pip_size
            formula = f"{price} {'+' if direction == Direction.LONG else '-'} {cfg.m_pips} * {self.pip_size}"

        layer_entry.close_price = close_price
        tp_pips = abs(close_price - layer_entry.entry_price) / self.pip_size
        layer_entry.expected_tp_pips = tp_pips
        layer_entry.validation_status = "pass"

        # Compute adverse pips from the previous layer's highest occupied slot
        if prev_layer_obj is not None:
            highest = prev_layer_obj.highest_occupied_slot()
            if highest is not None and highest.entry is not None:
                layer_entry.actual_interval_pips = (
                    abs(highest.entry.entry_price - price) / self.pip_size
                )

        logger.info(
            "Layer initial L%d/R0 in cycle %d, TP=%.3f",
            layer.layer_number,
            cycle.cycle_id,
            close_price,
        )

        evt = layer_entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Layer initial entry ({direction.value.upper()}) | "
                f"L{layer.layer_number}/R0, units={layer_entry.units}, TP={close_price:.3f}"
            ),
        )
        layer.initial_entry = layer_entry
        return [evt]

    # ------------------------------------------------------------------
    # Protection
    # ------------------------------------------------------------------

    def _handle_emergency(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
        unrealized: Decimal,
    ) -> tuple[list[StrategyEvent], str] | None:
        """Check for emergency stop. Returns (events, stop_reason) or None."""
        if ratio < Decimal("95"):
            return None
        ss.protection_level = ProtectionLevel.EMERGENCY
        all_entries = ss.all_entries()
        logger.critical(
            "EMERGENCY STOP: margin ratio %.1f%% >= 95%% | NAV=%s, entries=%d",
            ratio,
            ss.account_nav,
            len(all_entries),
        )
        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_STOPPED,
            timestamp=tick.timestamp,
            data={"kind": "emergency_stop", "ratio": str(ratio)},
        )
        event.strategy_type = "snowball"
        event.validation_status = "fail"
        return [event], f"Emergency stop: margin ratio {ratio:.1f}% >= 95%"

    def _handle_lock(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> list[StrategyEvent] | None:
        """Enter lock mode if ratio >= n_th. Returns events or None."""
        cfg = self.config
        if not cfg.lock_enabled or ratio < cfg.n_th:
            return None
        if ss.protection_level == ProtectionLevel.LOCKED:
            return None

        ss.protection_level = ProtectionLevel.LOCKED
        ss.lock_entered_at = tick.timestamp.isoformat()
        events: list[StrategyEvent] = []

        all_entries = ss.all_entries()
        long_units = sum(e.units for e in all_entries if e.is_long)
        short_units = sum(e.units for e in all_entries if e.is_short)
        net = long_units - short_units

        logger.warning(
            "LOCK MODE entered: margin ratio %.1f%% >= n_th=%.1f%%",
            ratio,
            cfg.n_th,
        )

        if net != 0:
            hedge_dir = Direction.SHORT if net > 0 else Direction.LONG
            hedge_units = abs(net)
            hedge_entry = Entry.open(
                state=ss,
                tick=tick,
                direction=hedge_dir,
                units=hedge_units,
                step=0,
                close_price=Decimal("0"),
                role="hedge",
                layer_number=0,
                retracement_count=0,
            )
            # Add hedge to the first active cycle (arbitrary; it's a global hedge)
            active = ss.active_cycles()
            if active:
                active[0].hedge_entries.append(hedge_entry)
            ss.lock_hedge_ids.append(hedge_entry.entry_id)

            open_evt = hedge_entry.to_open_event(
                timestamp=tick.timestamp,
                description=(
                    f"Lock hedge ({hedge_dir.value.upper()}) | "
                    f"[PROTECTION] units={hedge_units}, net={net}, ratio={ratio:.1f}%"
                ),
            )
            open_evt.basket = "hedge"
            open_evt.close_reason = "lock_hedge_open"
            open_evt.validation_status = "not_applicable"
            open_evt.step = 0
            events.append(open_evt)

        status_evt = GenericStrategyEvent(
            event_type=EventType.STATUS_CHANGED,
            timestamp=tick.timestamp,
            data={"kind": "snowball_locked", "ratio": str(ratio)},
        )
        status_evt.strategy_type = "snowball"
        status_evt.close_reason = "lock_entered"
        events.append(status_evt)
        return events

    def _handle_lock_release(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> list[StrategyEvent]:
        """Check if lock can be released. Returns events."""
        if ss.protection_level != ProtectionLevel.LOCKED:
            return []
        cfg = self.config
        unlock_ok = ratio < cfg.m_th - Decimal("5")
        if ss.cooldown_until:
            from datetime import datetime

            cd = datetime.fromisoformat(ss.cooldown_until)
            if tick.timestamp < cd:
                unlock_ok = False
        if not unlock_ok:
            return []

        events: list[StrategyEvent] = []
        for hid in list(ss.lock_hedge_ids):
            for cycle in ss.cycles:
                for e in list(cycle.hedge_entries):
                    if e.entry_id == hid:
                        events.append(
                            self._close_entry(
                                tick,
                                e,
                                description=f"[PROTECTION] Lock hedge unwound | ratio={ratio:.1f}%",
                                close_reason="lock_hedge_neutralize",
                                validation_status="not_applicable",
                            )
                        )
                        cycle.hedge_entries.remove(e)
        ss.lock_hedge_ids = []
        ss.lock_entered_at = None
        ss.cooldown_until = None
        ss.protection_level = (
            ProtectionLevel.SHRINK if ratio >= cfg.m_th else ProtectionLevel.NORMAL
        )
        unlock_evt = GenericStrategyEvent(
            event_type=EventType.STATUS_CHANGED,
            timestamp=tick.timestamp,
            data={"kind": "snowball_unlocked", "ratio": str(ratio)},
        )
        unlock_evt.strategy_type = "snowball"
        unlock_evt.close_reason = "lock_released"
        events.append(unlock_evt)
        return events

    def _handle_shrink(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> list[StrategyEvent] | None:
        """Shrink v2: close positions from oldest/smallest until margin ratio drops below m1_th.

        Close order per cycle:
        - L1 lowest R first, but skip the highest R in each layer
        - If a layer has only 1 position, close it
        - When L1/R0 is closed, move cycle initial_entry to the next closest open entry
        - Alternate between LONG and SHORT cycles, starting with the higher-impact one
        - If all positions are closed and ratio is still above m1_th, fail the task
        """
        cfg = self.config
        if not cfg.shrink_enabled or ratio < cfg.m_th:
            return None

        events: list[StrategyEvent] = []
        if ss.protection_level != ProtectionLevel.SHRINK:
            ss.protection_level = ProtectionLevel.SHRINK
            shrink_evt = GenericStrategyEvent(
                event_type=EventType.STATUS_CHANGED,
                timestamp=tick.timestamp,
                data={"kind": "snowball_shrink", "ratio": str(ratio)},
            )
            shrink_evt.strategy_type = "snowball"
            shrink_evt.close_reason = "shrink_entered"
            events.append(shrink_evt)

        closed_count = 0
        while ratio >= cfg.m1_th:
            # Pick the next entry to close, alternating between cycles
            entry, cycle = self._pick_shrink_target(ss, tick)
            if entry is None or cycle is None:
                # No more positions to close — fail the task
                logger.error(
                    "SHRINK EXHAUSTED: all positions closed but margin ratio "
                    "%.1f%% still above m1_th=%.1f%%. Failing task.",
                    ratio,
                    cfg.m1_th,
                )
                self._close_order_violation = (
                    f"Shrink exhausted: ratio={ratio:.1f}%, m1_th={cfg.m1_th}%, "
                    f"no more positions to close"
                )
                break

            # If closing L1/R0 (cycle initial), migrate initial_entry first
            if entry.entry_id == cycle.initial_entry.entry_id if cycle.initial_entry else False:
                self._migrate_cycle_initial(cycle, entry)

            events.append(
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"[PROTECTION] Shrink: L{entry.layer_number}/R{entry.retracement_count} | "
                        f"ratio={ratio:.1f}%, target={cfg.m1_th}%"
                    ),
                    close_reason="shrink",
                    validation_status="warn",
                )
            )
            cycle.remove_entry(entry.entry_id)
            closed_count += 1

            # Recalculate margin ratio after close
            # Approximate: each close reduces required margin
            from apps.trading.utils import quote_to_account_rate

            conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
            margin_rate = Decimal("0.04")
            released_margin = tick.mid * Decimal(str(abs(entry.units))) * margin_rate * conv
            nav = ss.account_nav
            if nav > 0:
                ratio = ratio - (released_margin / nav) * Decimal("100")

        if closed_count > 0:
            logger.warning(
                "SHRINK completed: closed %d position(s), ratio now ~%.1f%%",
                closed_count,
                ratio,
            )

        if ratio < cfg.m1_th:
            ss.protection_level = ProtectionLevel.NORMAL
        return events

    def _pick_shrink_target(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
    ) -> tuple[Entry | None, SnowballCycle | None]:
        """Pick the next position to close during shrink.

        Alternates between active cycles, starting with the one whose
        candidate has the largest unrealised loss (higher impact).
        Within a cycle: oldest layer, lowest R, skipping the highest R per layer.
        """
        candidates: list[tuple[Entry, SnowballCycle, Decimal]] = []
        for cycle in ss.active_cycles():
            entry = self._find_shrink_candidate_in_cycle(cycle)
            if entry is not None:
                loss = entry.unrealised_loss_pips(tick.mid, self.pip_size)
                candidates.append((entry, cycle, loss))

        if not candidates:
            return None, None

        # Pick the candidate with the largest loss (highest impact)
        candidates.sort(key=lambda c: c[2], reverse=True)
        return candidates[0][0], candidates[0][1]

    def _find_shrink_candidate_in_cycle(self, cycle: SnowballCycle) -> Entry | None:
        """Find the next entry to close in a cycle for shrink.

        Priority: preserve the highest R in each layer as long as possible.

        1. Scan layers bottom-up. If a layer has 2+ positions, return the
           lowest R (the highest R is preserved).
        2. If a layer has exactly 1 position, check whether any layer above
           it still has 2+ positions. If yes, skip this layer (the upper
           layer will yield a candidate first). If no (all layers above
           also have ≤1), this single position must be closed — return it.
        3. If no slot entries remain, return cycle.initial_entry.
        """
        layers = cycle.layers

        for i, layer in enumerate(layers):
            occupied = layer.occupied_slots()
            if not occupied:
                continue

            if len(occupied) >= 2:
                # Close the lowest R; preserve the highest R
                lowest = min(occupied, key=lambda s: s.index)
                return lowest.entry

            # Exactly 1 position in this layer.
            # Check if any layer above has 2+ occupied slots.
            has_multi_above = False
            for upper_layer in layers[i + 1 :]:
                if len(upper_layer.occupied_slots()) >= 2:
                    has_multi_above = True
                    break

            if has_multi_above:
                # Skip — upper layers still have positions to trim first
                continue

            # All layers above also have ≤1 position. Close this one.
            return occupied[0].entry

        # No slot entries left — check cycle initial_entry
        if cycle.initial_entry is not None:
            return cycle.initial_entry

        return None

    @staticmethod
    def _migrate_cycle_initial(cycle: SnowballCycle, old_initial: Entry) -> None:
        """Move cycle initial_entry to the next closest open entry.

        Called when shrink needs to close L1/R0. The next entry with the
        closest R number becomes the new initial_entry.
        """
        # Collect all open entries except the one being closed
        candidates: list[Entry] = []
        for layer in cycle.layers:
            for e in layer.all_entries():
                if e.entry_id != old_initial.entry_id:
                    candidates.append(e)

        if not candidates:
            # No other entries — cycle will end after this close
            cycle.initial_entry = None
            cycle.completed = True
            return

        # Pick the entry with the lowest layer number and lowest retracement count
        candidates.sort(key=lambda e: (e.layer_number, e.retracement_count))
        new_initial = candidates[0]
        logger.warning(
            "SHRINK: migrating cycle initial from entry_id=%s (L%s/R%s) to entry_id=%s (L%s/R%s)",
            old_initial.entry_id,
            old_initial.layer_number,
            old_initial.retracement_count,
            new_initial.entry_id,
            new_initial.layer_number,
            new_initial.retracement_count,
        )
        cycle.initial_entry = new_initial

    # ------------------------------------------------------------------
    # Core tick processing
    # ------------------------------------------------------------------

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        """Process a single tick."""
        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        ss.last_bid = tick.bid
        ss.last_ask = tick.ask
        ss.last_mid = tick.mid

        # Update NAV
        if state.current_balance:
            ss.account_balance = Decimal(str(state.current_balance))
        unrealized = Decimal("0")
        conv = quote_to_account_rate(self.instrument, tick.mid, self.account_currency)
        for entry in ss.all_entries():
            if entry.is_long:
                unrealized += (tick.bid - entry.entry_price) * Decimal(str(entry.units)) * conv
            else:
                unrealized += (entry.entry_price - tick.ask) * Decimal(str(entry.units)) * conv
        ss.account_nav = ss.account_balance + unrealized
        if ss.account_nav <= 0:
            ss.account_nav = ss.account_balance

        events: list[StrategyEvent] = []
        ratio = self._margin_ratio(state, ss)
        ss.metrics["margin_ratio"] = str(ratio / Decimal("100"))

        # --- Emergency ---
        emergency = self._handle_emergency(ss, tick, ratio, unrealized)
        if emergency is not None:
            emergency_events, stop_reason = emergency
            state.strategy_state = ss.to_dict()
            return StrategyResult(
                state=state,
                events=emergency_events,
                should_stop=True,
                stop_reason=stop_reason,
            )

        # --- Lock enter ---
        lock_events = self._handle_lock(ss, tick, ratio)
        if lock_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=lock_events)

        # --- Lock release ---
        if ss.protection_level == ProtectionLevel.LOCKED:
            release_events = self._handle_lock_release(ss, tick, ratio)
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=release_events)

        # --- Shrink ---
        shrink_events = self._handle_shrink(ss, tick, ratio)
        if shrink_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=shrink_events)

        # Back to normal
        if ss.protection_level != ProtectionLevel.NORMAL:
            ss.protection_level = ProtectionLevel.NORMAL

        # --- Initialisation ---
        if not ss.initialised:
            init_events, _ = self._create_cycle(ss, tick, Direction.LONG)
            events.extend(init_events)
            if self._hedging_enabled:
                short_events, _ = self._create_cycle(ss, tick, Direction.SHORT)
                events.extend(short_events)
            ss.initialised = True
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

        # --- Per-cycle processing ---
        for cycle in list(ss.active_cycles()):
            events.extend(self._process_cycle_tp(ss, tick, cycle))

            # Check if a close-order violation was detected
            if self._close_order_violation:
                state.strategy_state = ss.to_dict()
                return StrategyResult(
                    state=state,
                    events=events,
                    should_stop=True,
                    stop_reason=f"Close order violation: {self._close_order_violation}",
                )

            counter_close_events = self._process_cycle_counter_closes(ss, tick, cycle)
            events.extend(counter_close_events)
            # After a counter TP close the retracement count is reset to 0 and
            # the counter list is empty, so the "first counter add" path would
            # immediately re-enter on the same tick — creating an open/close
            # loop that fires every tick.  The spec says "re-enter on the *next*
            # adverse move", so we skip counter adds on the tick that closed.
            if not counter_close_events:
                events.extend(self._process_cycle_counter_adds(ss, tick, cycle))

        state.strategy_state = ss.to_dict()
        return StrategyResult(state=state, events=events)

    # ------------------------------------------------------------------
    # State serialisation
    # ------------------------------------------------------------------

    def apply_event_execution_result(
        self,
        *,
        state: ExecutionState,
        execution_result: EventExecutionResult,
    ) -> None:
        """Apply order execution feedback (position IDs) to state."""
        ss = SnowballStrategyState.from_strategy_state(state.strategy_state)
        if not execution_result:
            return

        binding = execution_result.entry_binding
        if binding is None:
            return
        eid = binding.entry_id
        position_id = binding.position_id
        if eid is None or position_id is None:
            return

        for cycle in ss.cycles:
            if cycle.initial_entry is not None and cycle.initial_entry.entry_id == eid:
                cycle.initial_entry.position_id = str(position_id)
            for layer in cycle.layers:
                if layer.initial_entry is not None and layer.initial_entry.entry_id == eid:
                    layer.initial_entry.position_id = str(position_id)
                for slot in layer.slots:
                    if slot.entry is not None and slot.entry.entry_id == eid:
                        slot.entry.position_id = str(position_id)
            for entry in cycle.hedge_entries:
                if entry.entry_id == eid:
                    entry.position_id = str(position_id)

        state.strategy_state = ss.to_dict()
