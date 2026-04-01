"""Trading engine for Snowball strategy.

Implements a cycle-based hedging strategy:
- Each cycle starts with an initial entry and tracks its own counter entries
- Hedging mode: LONG and SHORT cycles run independently in parallel
- Non-hedging mode: a single LONG cycle
- Multi-level margin protection (rebalance → shrink → lock → emergency)
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

    def _spread_pips(self, tick: Tick) -> Decimal:
        return (tick.ask - tick.bid) / self.pip_size

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
        layer1 = Layer.create(1, cfg.r_max, cfg.base_units)
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

    # ------------------------------------------------------------------
    # Per-cycle tick processing
    # ------------------------------------------------------------------

    def _process_cycle_tp(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Check if the initial entry hit its TP target."""
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
        return self._close_and_reenter(ss, tick, cycle)

    def _process_cycle_counter_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Check slot entries for TP hits, closing from highest slot down.

        Closes at most one entry per tick to avoid cascading.  When a slot
        entry is closed, the slot is vacated and marked ``ever_closed``.
        If the current layer becomes empty of slot entries, check whether
        the layer-initial entry (L2+) should also be closed.
        """
        if cycle.completed:
            return []

        # Walk layers from newest to oldest
        for layer in reversed(cycle.layers):
            highest = layer.highest_occupied_slot()
            if highest is None or highest.entry is None:
                continue

            entry = highest.entry
            close_price = entry.close_price
            if close_price <= 0:
                continue

            hit = False
            if entry.is_long and tick.bid >= close_price:
                hit = True
            elif entry.is_short and tick.ask <= close_price:
                hit = True
            if not hit:
                continue

            exit_price = entry.exit_price(tick)
            pips_gained = abs(exit_price - entry.entry_price) / self.pip_size
            ln = entry.layer_number
            ret = entry.retracement_count

            logger.info(
                "Counter TP (%s): L%s/R%s, +%.1f pips",
                entry.direction.value.upper(),
                ln,
                ret,
                pips_gained,
            )
            refillable = highest.index <= self.config.refill_up_to
            highest.vacate(refillable=refillable)
            cycle.counter_close_count += 1

            return [
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"Counter TP ({entry.direction.value.upper()}) | "
                        f"L{ln}/R{ret}, entry={entry.entry_price:.3f}, "
                        f"exit={exit_price:.3f}, +{pips_gained:.1f} pips"
                    ),
                    close_reason="counter_tp",
                    actual_tp_pips=pips_gained,
                    validation_status="pass",
                )
            ]

        # Check layer-initial entries (L2+) — close if layer has no slot entries
        for layer in reversed(cycle.layers):
            if layer.layer_number == 1:
                continue
            if layer.initial_entry is None:
                continue
            if layer.occupied_slots():
                break  # still has slot entries, don't close layer initial

            entry = layer.initial_entry
            close_price = entry.close_price
            if close_price <= 0:
                continue

            hit = False
            if entry.is_long and tick.bid >= close_price:
                hit = True
            elif entry.is_short and tick.ask <= close_price:
                hit = True
            if not hit:
                continue

            exit_price = entry.exit_price(tick)
            pips_gained = abs(exit_price - entry.entry_price) / self.pip_size
            ln = entry.layer_number

            logger.info(
                "Layer initial TP (%s): L%s, +%.1f pips",
                entry.direction.value.upper(),
                ln,
                pips_gained,
            )
            layer.initial_entry = None
            layer.reset()

            return [
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"Layer initial TP ({entry.direction.value.upper()}) | "
                        f"L{ln}, entry={entry.entry_price:.3f}, "
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
        """Check whether to add a new counter entry to this cycle.

        Uses the Layer/Slot model:
        1. Find the current layer's next empty slot.
        2. If the next slot has ``ever_closed`` (reversal happened), start a new layer.
        3. Measure adverse distance from the appropriate reference entry.
        4. If threshold met, fill the slot with a new entry.
        """
        if cycle.completed:
            return []
        cfg = self.config
        layer = cycle.current_layer
        if layer is None:
            return []

        # Check if we need a new layer
        if layer.should_start_new_layer():
            if cycle.layer_index >= cfg.f_max - 1:
                return []  # f_max reached
            return self._start_new_layer(ss, tick, cycle)

        # L2+ layers that were reset need their initial entry rebuilt first
        if layer.layer_number > 1 and layer.initial_entry is None:
            return self._rebuild_layer_initial(ss, tick, cycle, layer)

        # Find the next slot to fill
        slot = layer.next_slot_to_fill()
        if slot is None:
            return []

        # Check if initial entry is losing (gate check)
        initial = cycle.initial_entry
        if not initial:
            return []
        loss = initial.unrealised_loss_pips(tick.mid, self.pip_size)
        if loss <= 0:
            return []

        # Determine reference entry and adverse distance
        direction = cycle.direction
        occupied = layer.occupied_slots()
        if occupied:
            # Measure from the last filled slot's entry
            latest_entry = max(occupied, key=lambda s: s.index).entry
            assert latest_entry is not None
            if direction == Direction.LONG:
                adverse = (latest_entry.entry_price - tick.mid) / self.pip_size
            else:
                adverse = (tick.mid - latest_entry.entry_price) / self.pip_size
        else:
            # First slot in this layer — measure from layer initial
            reference = layer.initial_entry if layer.initial_entry is not None else initial
            adverse = reference.unrealised_loss_pips(tick.mid, self.pip_size)

        step_k = slot.index
        interval = counter_interval_pips(step_k, cfg)
        if adverse < interval:
            return []

        # Compute units: (slot_index + 1) * base_units
        lot_k = slot.index + 1
        units = lot_k * layer.base_units
        tp = counter_tp_pips(step_k, cfg)
        new_price = tick.ask if direction == Direction.LONG else tick.bid
        layer_number = layer.layer_number

        # Gather existing non-hedge entries in this layer for weighted avg
        layer_non_hedge = [
            s.entry for s in layer.slots if s.entry is not None and not s.entry.is_hedge
        ]
        close_price, exit_formula = self._compute_counter_tp(
            cfg,
            direction,
            new_price,
            units,
            tp,
            layer_non_hedge,
            layer.initial_entry if layer.layer_number > 1 else initial,
            current_layer=layer_number,
        )

        logger.info(
            "Counter add (%s) in cycle %d: L%d/R%d, units=%d, adverse=%.1f pips",
            direction.value.upper(),
            cycle.cycle_id,
            layer_number,
            slot.index,
            units,
            adverse,
        )
        entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=units,
            step=slot.index + 1,
            close_price=close_price,
            role="counter",
            layer_number=layer_number,
            retracement_count=slot.index,
            root_entry_id=initial.entry_id,
            parent_entry_id=initial.entry_id,
        )
        entry.expected_interval_pips = interval
        entry.actual_interval_pips = adverse
        entry.expected_tp_pips = tp
        entry.validation_status = "pass"
        evt = entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=exit_formula,
            description=(
                f"Counter add ({direction.value.upper()}) | "
                f"L{layer_number}/R{slot.index}, units={units}, "
                f"adverse={adverse:.1f} pips, TP={close_price:.3f}"
            ),
        )
        slot.fill(entry)

        # Update close prices for existing entries in this layer (non-weighted_avg only)
        if cfg.counter_tp_mode != "weighted_avg":
            for s in layer.slots:
                if s.entry is None or s.entry.is_hedge:
                    continue
                sk = s.index
                if sk < 1:
                    sk = 1
                step_tp = counter_tp_pips(sk, cfg)
                if direction == Direction.LONG:
                    s.entry.close_price = s.entry.entry_price + step_tp * self.pip_size
                else:
                    s.entry.close_price = s.entry.entry_price - step_tp * self.pip_size

        return [evt]

    def _start_new_layer(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Create a new layer with a layer-initial entry."""
        cfg = self.config
        initial = cycle.initial_entry
        if initial is None:
            return []

        direction = cycle.direction
        prev_layer = cycle.current_layer
        assert prev_layer is not None
        new_layer_number = prev_layer.layer_number + 1
        new_base_units = int(Decimal(str(cfg.base_units)) * cfg.post_r_max_base_factor)

        logger.info(
            "Starting new layer L%d in cycle %d",
            new_layer_number,
            cycle.cycle_id,
        )

        new_layer = Layer.create(new_layer_number, cfg.r_max, new_base_units)
        price = tick.ask if direction == Direction.LONG else tick.bid

        layer_entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=cfg.trend_lot_size * new_base_units,
            step=1,
            close_price=Decimal("0"),  # placeholder
            role="layer_initial",
            layer_number=new_layer_number,
            retracement_count=0,
            root_entry_id=initial.entry_id,
            parent_entry_id=initial.entry_id,
        )

        # Compute close_price as weighted average of previous layer's entries + this new entry
        prev_entries: list[tuple[Decimal, int]] = []
        prev_initial = cycle.initial_for_layer(prev_layer.layer_number)
        if prev_initial is not None:
            prev_entries.append((prev_initial.entry_price, abs(prev_initial.units)))
        for s in prev_layer.slots:
            if s.entry is not None and not s.entry.is_hedge:
                prev_entries.append((s.entry.entry_price, abs(s.entry.units)))
        prev_entries.append((layer_entry.entry_price, abs(layer_entry.units)))

        total_cost = sum(p * Decimal(str(u)) for p, u in prev_entries)
        total_units = sum(u for _, u in prev_entries)
        if total_units > 0:
            close_price = total_cost / Decimal(str(total_units))
        else:
            close_price = (
                price + cfg.m_pips * self.pip_size
                if direction == Direction.LONG
                else price - cfg.m_pips * self.pip_size
            )

        layer_entry.close_price = close_price
        tp_pips = abs(close_price - layer_entry.entry_price) / self.pip_size
        layer_entry.expected_tp_pips = tp_pips
        layer_entry.validation_status = "pass"
        formula = f"weighted_avg(L{prev_layer.layer_number} entries + L{new_layer_number} initial)"
        evt = layer_entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Layer initial entry ({direction.value.upper()}) | "
                f"L{new_layer_number}/R0, units={layer_entry.units}, TP={close_price:.3f}"
            ),
        )
        new_layer.initial_entry = layer_entry
        cycle.add_layer(new_layer)
        return [evt]

    def _rebuild_layer_initial(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
        layer: Layer,
    ) -> list[StrategyEvent]:
        """Rebuild the initial entry for a reset L2+ layer."""
        cfg = self.config
        initial = cycle.initial_entry
        if initial is None:
            return []

        direction = cycle.direction
        layer_number = layer.layer_number
        price = tick.ask if direction == Direction.LONG else tick.bid

        layer_entry = Entry.open(
            state=ss,
            tick=tick,
            direction=direction,
            units=cfg.trend_lot_size * layer.base_units,
            step=1,
            close_price=Decimal("0"),
            role="layer_initial",
            layer_number=layer_number,
            retracement_count=0,
            root_entry_id=initial.entry_id,
            parent_entry_id=initial.entry_id,
        )

        # Compute close_price from previous layer's entries + this new entry
        prev_layer_num = layer_number - 1
        prev_entries: list[tuple[Decimal, int]] = []
        prev_initial = cycle.initial_for_layer(prev_layer_num)
        if prev_initial is not None:
            prev_entries.append((prev_initial.entry_price, abs(prev_initial.units)))
        for ly in cycle.layers:
            if ly.layer_number == prev_layer_num:
                for s in ly.slots:
                    if s.entry is not None and not s.entry.is_hedge:
                        prev_entries.append((s.entry.entry_price, abs(s.entry.units)))
        prev_entries.append((layer_entry.entry_price, abs(layer_entry.units)))

        total_cost = sum(p * Decimal(str(u)) for p, u in prev_entries)
        total_units = sum(u for _, u in prev_entries)
        if total_units > 0:
            close_price = total_cost / Decimal(str(total_units))
        else:
            close_price = (
                price + cfg.m_pips * self.pip_size
                if direction == Direction.LONG
                else price - cfg.m_pips * self.pip_size
            )

        layer_entry.close_price = close_price
        tp_pips = abs(close_price - layer_entry.entry_price) / self.pip_size
        layer_entry.expected_tp_pips = tp_pips
        layer_entry.validation_status = "pass"
        formula = f"weighted_avg(L{prev_layer_num} entries + L{layer_number} initial rebuild)"

        logger.info(
            "Rebuilding layer initial L%d/R0 in cycle %d",
            layer_number,
            cycle.cycle_id,
        )

        evt = layer_entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Layer initial entry ({direction.value.upper()}) | "
                f"L{layer_number}/R0, units={layer_entry.units}, TP={close_price:.3f}"
            ),
        )
        layer.initial_entry = layer_entry
        return [evt]

    def _compute_counter_tp(
        self,
        cfg: SnowballStrategyConfig,
        direction: Direction,
        new_price: Decimal,
        units: int,
        tp: Decimal,
        counter_non_hedge: list[Entry],
        layer_initial: Entry | None,
        current_layer: int = 1,
    ) -> tuple[Decimal, str]:
        """Compute close_price and formula for a counter add."""
        if cfg.counter_tp_mode == "weighted_avg":
            total_u = units
            total_cost = new_price * Decimal(str(units))
            formula_parts = [f"{new_price} * {units}"]
            for e in counter_non_hedge:
                if e.layer_number != current_layer:
                    continue
                total_u += e.units
                total_cost += e.entry_price * Decimal(str(e.units))
                formula_parts.append(f"{e.entry_price} * {e.units}")
            if layer_initial is not None:
                ie_units = abs(layer_initial.units)
                if ie_units > 0:
                    total_u += ie_units
                    total_cost += layer_initial.entry_price * Decimal(str(ie_units))
                    formula_parts.append(f"{layer_initial.entry_price} * {ie_units}")
            close_price = total_cost / Decimal(str(total_u)) if total_u > 0 else new_price
            exit_formula = f"({' + '.join(formula_parts)}) / {total_u}"
        else:
            if direction == Direction.LONG:
                close_price = new_price + tp * self.pip_size
            else:
                close_price = new_price - tp * self.pip_size
            op = "+" if direction == Direction.LONG else "-"
            exit_formula = f"{new_price} {op} {tp} * {self.pip_size}"
        return close_price, exit_formula

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
        unlock_ok = ratio < cfg.m_th - Decimal("5") and (
            not cfg.spread_guard_enabled or self._spread_pips(tick) <= cfg.spread_guard_pips
        )
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
        """Shrink mode: close worst-loss counter entry. Returns events or None."""
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

        # Find worst-loss counter entry across all cycles
        worst_entry: Entry | None = None
        worst_cycle: SnowballCycle | None = None
        worst_loss = Decimal("-1")
        for cycle in ss.active_cycles():
            for e in cycle.counter_entries:
                if e.is_hedge:
                    continue
                loss = e.unrealised_loss_pips(tick.mid, self.pip_size)
                if loss > worst_loss:
                    worst_loss = loss
                    worst_entry = e
                    worst_cycle = cycle

        if worst_entry and worst_cycle:
            events.append(
                self._close_entry(
                    tick,
                    worst_entry,
                    description=(
                        f"[PROTECTION] Shrink: close largest-loss counter | "
                        f"loss={worst_loss:.1f} pips, ratio={ratio:.1f}%"
                    ),
                    close_reason="shrink",
                    validation_status="warn",
                )
            )
            worst_cycle.remove_entry(worst_entry.entry_id)

        if ratio < cfg.m_th - Decimal("5"):
            ss.protection_level = ProtectionLevel.NORMAL
        return events

    def _handle_rebalance(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> list[StrategyEvent] | None:
        """Rebalance: reduce BUY/SELL imbalance. Returns events or None."""
        cfg = self.config
        if not cfg.rebalance_enabled or ratio < cfg.rebalance_start_ratio:
            return None

        events: list[StrategyEvent] = []
        all_entries = ss.all_entries()
        long_units = sum(e.units for e in all_entries if e.is_long)
        short_units = sum(e.units for e in all_entries if e.is_short)
        if long_units == short_units:
            return events

        heavier = Direction.LONG if long_units > short_units else Direction.SHORT
        # Collect all counter entries on the heavier side, sorted by step
        candidates: list[tuple[SnowballCycle, Entry]] = []
        for cycle in ss.active_cycles():
            for e in cycle.counter_entries:
                if e.direction == heavier and not e.is_hedge:
                    candidates.append((cycle, e))
        candidates.sort(key=lambda x: x[1].step)

        for cycle, entry in candidates:
            events.append(
                self._close_entry(
                    tick,
                    entry,
                    description=(
                        f"[PROTECTION] Rebalance: reduce {heavier.value.upper()} imbalance | "
                        f"LONG={long_units} vs SHORT={short_units}"
                    ),
                    close_reason="rebalance",
                    validation_status="warn",
                )
            )
            cycle.remove_entry(entry.entry_id)
            # Recheck
            all_entries = ss.all_entries()
            long_units = sum(e.units for e in all_entries if e.is_long)
            short_units = sum(e.units for e in all_entries if e.is_short)
            if long_units == short_units:
                break
        return events

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

        # --- Rebalance ---
        rebalance_events = self._handle_rebalance(ss, tick, ratio)
        if rebalance_events is not None:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=rebalance_events)

        # Back to normal
        if ss.protection_level != ProtectionLevel.NORMAL:
            ss.protection_level = ProtectionLevel.NORMAL

        # --- Spread guard ---
        cfg = self.config
        if cfg.spread_guard_enabled and self._spread_pips(tick) > cfg.spread_guard_pips:
            state.strategy_state = ss.to_dict()
            return StrategyResult(state=state, events=events)

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
