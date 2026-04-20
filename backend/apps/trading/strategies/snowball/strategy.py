"""Trading engine for Snowball strategy.

Implements a cycle-based hedging strategy:
- Each cycle starts with an initial entry and tracks its own counter entries
- Hedging mode: LONG and SHORT cycles run independently in parallel
- Non-hedging mode: a single LONG cycle
- Multi-level margin protection (shrink → lock → emergency)

Position grid
-------------
All positions (including the cycle's first entry) live in a unified
``PositionGrid``.  The grid is addressed as L(layer)/R(index) where both
are 0-based.  R0 of each layer is the layer-initial position.

Close ordering:
- Normal TP: newest → oldest (back of grid first)
- Shrink protection: oldest → newest (front of grid first)
- Cycle head (whose TP ends the cycle): dynamically the oldest surviving
  position — ``grid.head_entry()``.
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
    stop_loss_price,
)
from apps.trading.strategies.snowball.enums import CycleStatus, ProtectionLevel
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    Slot,
    SnowballCycle,
    SnowballStrategyConfig,
    SnowballStrategyState,
    StopLossClosedEntry,
)
from apps.trading.utils import format_money, quote_to_account_rate

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
        self._grid_order_violation: str | None = None
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

    def _close_entry(
        self,
        tick: Tick,
        entry: Entry,
        *,
        description: str = "",
        close_reason: str = "",
        actual_tp_pips: Decimal | None = None,
        validation_status: str = "",
        margin_ratio: Decimal | None = None,
        cycle: SnowballCycle | None = None,
    ) -> ClosePositionEvent:
        """Create a ClosePositionEvent from an Entry and emit sanity warnings.

        Updates ``entry.lifecycle_realized_pnl`` with this close's P/L and,
        when ``cycle`` is provided, adds the same delta to
        ``cycle.realized_pnl``.  Emits a ``logger.warning`` in two cases:

        1. A non-stop-loss close ends with negative P/L for this slot's full
           open → (optional stop-loss → rebuild)+ → close chain.  Open →
           close without any stop-loss is the degenerate case of the same
           check and is covered automatically.
        2. A stop-loss is not expected to be profitable, so it never trips
           the warning on its own, but it still accumulates into the
           lifecycle total so the eventual rebuild-close comparison is
           apples-to-apples.
        """
        event = entry.to_close_event(
            tick,
            instrument=self.instrument,
            pip_size=self.pip_size,
            account_currency=self.account_currency,
            description=description,
            close_reason=close_reason,
            actual_tp_pips=actual_tp_pips,
            validation_status=validation_status,
        )
        if margin_ratio is not None:
            event.margin_ratio = margin_ratio

        # Accumulate P/L at the slot-lifecycle and cycle level.
        delta_pnl = event.pnl
        entry.lifecycle_realized_pnl += delta_pnl
        if cycle is not None:
            cycle.realized_pnl += delta_pnl

        # Warning 1: single close is negative and is not a stop-loss.
        # Stop-losses are, by definition, losing closes so they do not
        # warrant a warning on their own.
        if close_reason != "stop_loss" and delta_pnl < 0:
            logger.warning(
                "Close with negative P/L (reason=%s): entry_id=%s position_id=%s "
                "L%d/R%d %s entry=%s exit=%s units=%s pnl=%s",
                close_reason or "unknown",
                entry.entry_id,
                entry.position_id or "-",
                entry.layer_number,
                entry.retracement_count,
                entry.direction.value.upper(),
                entry.entry_price,
                event.exit_price,
                entry.units,
                format_money(delta_pnl),
            )

        # Warning 2: slot lifecycle (open → *SL → rebuild → close)
        # finishes negative.  Only emitted on non-stop-loss closes —
        # intermediate stop-losses are expected to push the running
        # total negative.
        if (
            close_reason != "stop_loss"
            and entry.lifecycle_stop_loss_count > 0
            and entry.lifecycle_realized_pnl < 0
        ):
            logger.warning(
                "Slot lifecycle closed with negative net P/L: entry_id=%s "
                "position_id=%s L%d/R%d %s stop_losses=%d net_pnl=%s "
                "(final_close_reason=%s)",
                entry.entry_id,
                entry.position_id or "-",
                entry.layer_number,
                entry.retracement_count,
                entry.direction.value.upper(),
                entry.lifecycle_stop_loss_count,
                format_money(entry.lifecycle_realized_pnl),
                close_reason or "unknown",
            )

        return event

    # ------------------------------------------------------------------
    # Cycle lifecycle
    # ------------------------------------------------------------------

    def _create_cycle(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        direction: Direction,
    ) -> tuple[list[StrategyEvent], SnowballCycle]:
        """Create a new cycle with an initial entry at L0/R0."""
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
            layer_number=1,
            retracement_count=0,
        )
        entry.expected_tp_pips = cfg.m_pips
        entry.validation_status = "pass"

        # Compute stop-loss for this entry at creation time
        if cfg.stop_loss_enabled:
            next_interval = counter_interval_pips(1, cfg)
            if next_interval > 0:
                self._assign_stop_loss(entry, next_interval)

        evt = entry.to_open_event(
            timestamp=tick.timestamp,
            planned_exit_price_formula=formula,
            description=(
                f"Initial entry ({direction.value.upper()}) | units={units}, TP={close_price:.3f}"
                + (f", SL={entry.stop_loss_price:.3f}" if entry.stop_loss_price is not None else "")
            ),
        )

        cycle = SnowballCycle(cycle_id=entry.entry_id, direction=direction)
        # L1 with R0 (initial) + R1…R(r_max) counter slots
        layer0 = Layer.create(1, cfg.r_max, cfg.base_units, cfg.refill_up_to)
        slot0 = layer0.slot_at(0)
        assert slot0 is not None  # noqa: S101
        slot0.fill(entry)
        cycle.add_layer(layer0)
        ss.cycles.append(cycle)
        return [evt], cycle

    def _close_and_reenter(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Close the cycle's R0 (TP hit) and create a new cycle.

        This is only called when the cycle TP (R0.entry_price ± m_pips)
        is reached and R0 is a live entry.  The cycle transitions to
        COMPLETED via the unified status check in on_tick.
        """
        # Find R0 entry in L1
        layer = cycle.grid.layers[0] if cycle.grid.layers else None
        if layer is None:
            return []
        r0_slot = layer.slot_at(0)
        if r0_slot is None or r0_slot.entry is None:
            return []

        entry = r0_slot.entry
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
                cycle=cycle,
            )
        )

        # Close R0 slot — not refillable (cycle is ending).
        layer.close_slot(0, refillable=False)

        # Do NOT clear pending rebuilds here.  If other slots have
        # pending rebuilds, the cycle status update in on_tick will
        # transition the cycle to PENDING (not COMPLETED).  Those
        # rebuilds will eventually restore positions and close them
        # normally, at which point the cycle will finally complete.

        # Only create a new cycle if no other ACTIVE cycle exists for
        # this direction.  When multiple cycles coexist (e.g. after SL
        # rebuild reactivation), each TP close used to spawn a new
        # cycle, causing exponential proliferation.  The re-seed logic
        # at the end of on_tick will create exactly one new cycle when
        # the direction has zero active/pending cycles.
        has_other_active = any(
            c.is_active and c.cycle_id != cycle.cycle_id and c.direction == direction
            for c in ss.active_cycles()
        )
        if not has_other_active:
            new_events, _new_cycle = self._create_cycle(ss, tick, direction)
            logger.info(
                "Re-entry (%s) after TP: new cycle_id=%d",
                direction.value.upper(),
                _new_cycle.cycle_id,
            )
            events.extend(new_events)
        else:
            logger.info(
                "TP (%s) cycle %d — skipping re-entry, other active cycle(s) exist",
                direction.value.upper(),
                cycle.cycle_id,
            )

        return events

    def _fail_close_order_violation(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Build a stop event when a close-order violation is detected."""
        open_entries = []
        for e in cycle.grid.all_entries():
            open_entries.append(
                f"L{e.layer_number}/R{e.retracement_count} "
                f"entry={e.entry_price:.3f} tp={e.close_price:.3f}"
            )
        head = cycle.initial_entry
        head_price = f"{head.entry_price:.3f}" if head else "None"
        head_tp = f"{head.close_price:.3f}" if head else "None"
        detail = (
            f"cycle_id={cycle.cycle_id}, direction={cycle.direction.value}, "
            f"head_entry={head_price}, head_tp={head_tp}, "
            f"open_entries=[{', '.join(open_entries)}], "
            f"tick_bid={tick.bid}, tick_ask={tick.ask}"
        )
        logger.error("Close order violation detail: %s", detail)
        self._close_order_violation = detail
        return []

    def _validate_grid_ordering(self, cycle: SnowballCycle) -> None:
        """Ensure present slots preserve monotonic entry/TP ordering."""
        present: list[tuple[int, int, Decimal, Decimal, str]] = []
        for layer in cycle.grid.layers:
            for slot in layer.slots:
                if slot.entry is not None:
                    present.append(
                        (
                            layer.layer_number,
                            slot.index,
                            slot.entry.entry_price,
                            slot.entry.close_price,
                            "open",
                        )
                    )
                elif slot.pending_rebuild is not None:
                    pending = slot.pending_rebuild
                    present.append(
                        (
                            layer.layer_number,
                            slot.index,
                            pending.entry_price,
                            pending.close_price,
                            "pending_rebuild",
                        )
                    )

        if len(present) < 2:
            return

        for prev, curr in zip(present, present[1:], strict=False):
            if cycle.is_long:
                entry_ok = prev[2] >= curr[2]
                tp_ok = prev[3] >= curr[3]
                expected = "descending"
            else:
                entry_ok = prev[2] <= curr[2]
                tp_ok = prev[3] <= curr[3]
                expected = "ascending"

            if entry_ok and tp_ok:
                continue

            self._grid_order_violation = (
                f"cycle_id={cycle.cycle_id}, direction={cycle.direction.value}, expected={expected}, "
                f"prev=L{prev[0]}/R{prev[1]}({prev[4]}) entry={prev[2]:.5f} tp={prev[3]:.5f}, "
                f"curr=L{curr[0]}/R{curr[1]}({curr[4]}) entry={curr[2]:.5f} tp={curr[3]:.5f}, "
                f"entry_ok={entry_ok}, tp_ok={tp_ok}"
            )
            logger.error("Grid ordering violation detail: %s", self._grid_order_violation)
            return

    def _upper_neighbor_tp_bound(self, layer: "Layer", slot_index: int) -> Decimal | None:
        """Return the TP of the nearest present slot above ``slot_index``.

        "Present" means occupied (``slot.entry`` set) or pending rebuild.
        Returns ``None`` when no such neighbor exists, in which case the
        rebuilt slot has no in-layer upper bound to respect.  This is
        used by the SL-rebuild path to clamp ``adjusted_close_price`` so
        the grid stays monotonic and ``_validate_grid_ordering`` keeps
        passing after the rebuild completes.
        """
        upper_tp: Decimal | None = None
        for s in layer.slots:
            if s.index >= slot_index:
                continue
            if s.entry is not None:
                upper_tp = s.entry.close_price
            elif s.pending_rebuild is not None:
                upper_tp = s.pending_rebuild.close_price
        return upper_tp

    # ------------------------------------------------------------------
    # Per-cycle tick processing
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_side_price(direction: Direction, tick: Tick) -> Decimal:
        """Return the executable entry-side price for a direction."""
        return tick.ask if direction == Direction.LONG else tick.bid

    @staticmethod
    def _exit_side_price(direction: Direction, tick: Tick) -> Decimal:
        """Return the executable exit-side price for a direction."""
        return tick.bid if direction == Direction.LONG else tick.ask

    def _process_cycle_tp(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Check if the cycle's R0 TP target is hit.

        The cycle TP is always based on the *original* R0 entry price
        (or its pending-rebuild snapshot when R0 has been stopped out).
        This is ``R0.entry_price ± m_pips * pip_size``.

        The R0 position can only close when no other entries remain open
        in the grid.  If counter entries are still present, their TPs
        should be reached first (they are closer to the current price).
        """
        if cycle.completed:
            return []

        direction = cycle.direction
        cfg = self.config

        # Determine R0's entry price — live entry or pending-rebuild snapshot.
        layer = cycle.grid.layers[0] if cycle.grid.layers else None
        if layer is None:
            return []
        r0_slot = layer.slot_at(0)
        if r0_slot is None:
            return []

        r0_entry = r0_slot.entry
        r0_pending = r0_slot.pending_rebuild
        if r0_entry is not None:
            r0_price = r0_entry.entry_price
        elif r0_pending is not None:
            r0_price = r0_pending.entry_price
        else:
            return []

        # Check if cycle TP is hit based on R0's entry price.
        hit = False
        if direction == Direction.LONG and tick.bid >= r0_price + cfg.m_pips * self.pip_size:
            hit = True
        elif direction == Direction.SHORT and tick.ask <= r0_price - cfg.m_pips * self.pip_size:
            hit = True

        if not hit:
            return []

        # R0 must be a live entry to close it.  If R0 is pending rebuild,
        # the TP region is reached but we cannot close — just log and
        # wait for the rebuild to complete.
        if r0_entry is None:
            logger.info(
                "Cycle TP region reached (%s) but R0 is pending rebuild — waiting",
                direction.value.upper(),
            )
            return []

        if not cycle.grid.has_counter_entries():
            return self._close_and_reenter(ss, tick, cycle)

        # Counter entries are still open while the head TP is hit.
        # Check whether every remaining counter's TP is also reached
        # on this tick.  If so, flush them all and proceed normally.
        all_counters_tp_hit = True
        for e in cycle.grid.all_entries():
            if e.entry_id == r0_entry.entry_id:
                continue
            if e.close_price <= 0:
                all_counters_tp_hit = False
                break
            if e.is_long and tick.bid < e.close_price:
                all_counters_tp_hit = False
                break
            if e.is_short and tick.ask > e.close_price:
                all_counters_tp_hit = False
                break

        if not all_counters_tp_hit:
            logger.warning(
                "Head TP reached while some counter TPs are not yet hit — "
                "force-closing remaining entries at market price. "
                "cycle_id=%d, direction=%s.",
                cycle.cycle_id,
                direction.value,
            )

        # Flush all remaining counter entries.
        events: list[StrategyEvent] = []
        for layer_iter in reversed(list(cycle.grid.layers)):
            for slot in reversed(layer_iter.occupied_slots()):
                counter = slot.entry
                if counter is None or counter.entry_id == r0_entry.entry_id:
                    continue
                tp_hit = True
                if counter.close_price <= 0:
                    tp_hit = False
                elif counter.is_long and tick.bid < counter.close_price:
                    tp_hit = False
                elif counter.is_short and tick.ask > counter.close_price:
                    tp_hit = False

                exit_price = counter.exit_price(tick)
                pips_gained = abs(exit_price - counter.entry_price) / self.pip_size
                if tp_hit:
                    label = "Counter TP flush"
                    reason = "counter_tp"
                    status = "pass"
                else:
                    label = "Counter force-close (head TP)"
                    reason = "counter_tp"
                    status = "warn"
                logger.info(
                    "%s (%s): L%s/R%s, %.1f pips",
                    label,
                    counter.direction.value.upper(),
                    counter.layer_number,
                    counter.retracement_count,
                    pips_gained if tp_hit else -pips_gained,
                )
                layer_iter.close_slot(slot.index)
                cycle.counter_close_count += 1
                events.append(
                    self._close_entry(
                        tick,
                        counter,
                        description=(
                            f"{label} ({counter.direction.value.upper()}) | "
                            f"L{counter.layer_number}/R{counter.retracement_count}, "
                            f"entry={counter.entry_price:.3f}, "
                            f"exit={exit_price:.3f}, {'+' if tp_hit else ''}{pips_gained:.1f} pips"
                        ),
                        close_reason=reason,
                        actual_tp_pips=pips_gained,
                        validation_status=status,
                        cycle=cycle,
                    )
                )
            # Remove empty non-L1 layers
            if layer_iter.layer_number > 1 and not layer_iter.has_open_entries():
                cycle.grid.layers.remove(layer_iter)

        events.extend(self._close_and_reenter(ss, tick, cycle))
        return events

    def _process_cycle_counter_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Close counter entries from the back (newest first), one per tick.

        Any entry whose close_price (counter TP) is reached gets closed,
        regardless of whether it is currently the dynamic head.  The only
        exception is L1/R0 — the original cycle head — which closes via
        _process_cycle_tp (cycle TP = R0.entry_price ± m_pips).

        After all counter slots in a non-L1 layer are empty, close the
        layer's R0 (layer-initial) if its TP is hit, then remove the layer.
        """
        if cycle.completed:
            return []

        # Walk layers from newest to oldest — close highest occupied counter slot
        for layer in reversed(cycle.grid.layers):
            highest = layer.highest_occupied_slot()
            if highest is None or highest.entry is None:
                continue

            entry = highest.entry

            # Skip L1/R0 — it closes via _process_cycle_tp (cycle TP).
            if entry.layer_number == 1 and entry.retracement_count == 0:
                continue

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

            # When a higher-layer R0 is the only live slot left, it can be
            # selected directly by the generic back-to-front TP close above.
            # Remove that now-empty layer immediately; otherwise the next
            # counter add sees the stale empty layer as current and resumes at
            # R1, leaving an impossible-looking "hole" at R0.
            if layer.layer_number > 1 and highest.index == 0 and not layer.has_open_entries():
                cycle.grid.layers.remove(layer)

            events: list[StrategyEvent] = [
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
                    cycle=cycle,
                )
            ]

            # If this was the last counter slot in a non-L1 layer and R0 is
            # the only remaining entry, check if R0's TP is also hit.
            # If so, close R0 and remove the layer.
            if layer.layer_number > 1:
                remaining = layer.occupied_slots()
                if len(remaining) == 1 and remaining[0].index == 0:
                    r0_entry = remaining[0].entry
                    if r0_entry is not None and r0_entry.close_price > 0:
                        r0_hit = False
                        if r0_entry.is_long and tick.bid >= r0_entry.close_price:
                            r0_hit = True
                        elif r0_entry.is_short and tick.ask <= r0_entry.close_price:
                            r0_hit = True
                        if r0_hit:
                            r0_exit = r0_entry.exit_price(tick)
                            r0_pips = abs(r0_exit - r0_entry.entry_price) / self.pip_size
                            logger.info(
                                "Layer initial TP (%s): L%s, +%.1f pips — removing layer",
                                r0_entry.direction.value.upper(),
                                layer.layer_number,
                                r0_pips,
                            )
                            layer.close_slot(0, refillable=False)
                            cycle.grid.layers.remove(layer)
                            events.append(
                                self._close_entry(
                                    tick,
                                    r0_entry,
                                    description=(
                                        f"Layer initial TP ({r0_entry.direction.value.upper()}) | "
                                        f"L{layer.layer_number}, entry={r0_entry.entry_price:.3f}, "
                                        f"exit={r0_exit:.3f}, +{r0_pips:.1f} pips"
                                    ),
                                    close_reason="layer_initial_tp",
                                    actual_tp_pips=r0_pips,
                                    validation_status="pass",
                                    cycle=cycle,
                                )
                            )

            return events

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

        head = cycle.initial_entry

        # When all live entries have been stop-loss closed, head is None.
        # Fall back to the R0 pending-rebuild snapshot so counter adds can
        # still proceed within the same cycle.
        head_entry_price: Decimal | None = None
        head_entry_id: int | None = None
        head_direction: Direction = cycle.direction
        if head is not None:
            head_entry_price = head.entry_price
            head_entry_id = head.entry_id
        else:
            r0 = layer.slot_at(0)
            if r0 is not None and r0.pending_rebuild is not None:
                head_entry_price = r0.pending_rebuild.entry_price
                head_entry_id = r0.pending_rebuild.root_entry_id
            else:
                return []

        def _head_losing() -> bool:
            """Check if the cycle head (or its SL snapshot) is in a losing position."""
            if head is not None:
                return (
                    head.unrealised_loss_pips(
                        self._exit_side_price(head.direction, tick),
                        self.pip_size,
                    )
                    > 0
                )
            # Fallback: compute from pending-rebuild entry price
            assert head_entry_price is not None  # noqa: S101
            if head_direction == Direction.LONG:
                return (
                    head_entry_price - self._exit_side_price(head_direction, tick)
                ) / self.pip_size > 0
            return (
                self._exit_side_price(head_direction, tick) - head_entry_price
            ) / self.pip_size > 0

        # Need a new layer?
        if layer.needs_new_layer:
            if cycle.layer_count >= cfg.f_max:
                return []

            # Gate: head must be losing
            if not _head_losing():
                return []

            # Gate: price must have moved adversely from the highest
            # present slot (occupied or pending rebuild) in the current
            # layer.  When the reference slot was filled on *this* tick
            # (by an earlier same-tick counter-add iteration), compare
            # against the design cumulative-from-R0 position instead,
            # otherwise ``adverse`` collapses to zero.
            direction = cycle.direction
            highest = layer.highest_present_slot()
            if highest is not None:
                ref_price = (
                    highest.entry.entry_price
                    if highest.entry is not None
                    else highest.pending_rebuild.entry_price
                    if highest.pending_rebuild is not None
                    else None
                )
                fresh_same_tick = (
                    highest.entry is not None and highest.entry.opened_at == tick.timestamp
                )
                if fresh_same_tick:
                    r0_slot = layer.slot_at(0)
                    r0_ref_price: Decimal | None = None
                    if r0_slot is not None:
                        if r0_slot.entry is not None:
                            r0_ref_price = r0_slot.entry.entry_price
                        elif r0_slot.pending_rebuild is not None:
                            r0_ref_price = r0_slot.pending_rebuild.entry_price
                    if r0_ref_price is not None:
                        cumulative_interval = Decimal("0")
                        for k in range(1, highest.index + 2):
                            cumulative_interval += counter_interval_pips(k, cfg)
                        current_entry_price = self._entry_side_price(direction, tick)
                        if direction == Direction.LONG:
                            adverse = (r0_ref_price - current_entry_price) / self.pip_size
                        else:
                            adverse = (current_entry_price - r0_ref_price) / self.pip_size
                        if adverse < cumulative_interval:
                            return []
                elif ref_price is not None:
                    current_entry_price = self._entry_side_price(direction, tick)
                    if direction == Direction.LONG:
                        adverse = (ref_price - current_entry_price) / self.pip_size
                    else:
                        adverse = (current_entry_price - ref_price) / self.pip_size
                    interval = counter_interval_pips(highest.index + 1, cfg)
                    if adverse < interval:
                        return []

            return self._open_layer_initial(ss, tick, cycle)

        # Find the next available counter slot (R1+)
        slot = layer.next_available_counter_slot()
        if slot is None:
            return []

        # Gate: head must be losing
        if not _head_losing():
            return []

        # Measure adverse distance from the highest present slot
        # (occupied or pending rebuild).  SL-closed positions still
        # count for R-number progression — the next counter must be
        # placed at the correct interval from the last known position.
        #
        # Same-tick counter-add loop special case: when the most recent
        # previous slot was opened on *this* tick, its market fill price
        # equals the current tick price, which would collapse ``adverse``
        # to zero and stall the loop.  In that case, compare against the
        # layer's R0 + cumulative design interval instead.
        direction = cycle.direction
        previous_slot = layer.previous_present_slot(slot.index)
        fresh_same_tick = (
            previous_slot is not None
            and previous_slot.entry is not None
            and previous_slot.entry.opened_at == tick.timestamp
        )

        if fresh_same_tick:
            r0_slot = layer.slot_at(0)
            r0_ref_price: Decimal | None = None
            if r0_slot is not None:
                if r0_slot.entry is not None:
                    r0_ref_price = r0_slot.entry.entry_price
                elif r0_slot.pending_rebuild is not None:
                    r0_ref_price = r0_slot.pending_rebuild.entry_price
            if r0_ref_price is None:
                r0_ref_price = head_entry_price
            if r0_ref_price is None:
                return []
            cumulative_interval = Decimal("0")
            for k in range(1, slot.index + 1):
                cumulative_interval += counter_interval_pips(k, cfg)
            current_entry_price = self._entry_side_price(direction, tick)
            if direction == Direction.LONG:
                adverse = (r0_ref_price - current_entry_price) / self.pip_size
            else:
                adverse = (current_entry_price - r0_ref_price) / self.pip_size
            interval = counter_interval_pips(slot.index, cfg)
            if adverse < cumulative_interval:
                return []
        else:
            if previous_slot is not None:
                ref_price: Decimal | None = (
                    previous_slot.entry.entry_price
                    if previous_slot.entry is not None
                    else previous_slot.pending_rebuild.entry_price
                    if previous_slot.pending_rebuild is not None
                    else None
                )
            else:
                # First counter in this layer — measure from R0
                r0 = layer.slot_at(0)
                if r0 is not None and r0.entry is not None:
                    ref_price = r0.entry.entry_price
                elif r0 is not None and r0.pending_rebuild is not None:
                    ref_price = r0.pending_rebuild.entry_price
                else:
                    ref_price = head_entry_price

            if ref_price is None:
                return []
            current_entry_price = self._entry_side_price(direction, tick)
            if direction == Direction.LONG:
                adverse = (ref_price - current_entry_price) / self.pip_size
            else:
                adverse = (current_entry_price - ref_price) / self.pip_size

            interval = counter_interval_pips(slot.index, cfg)
            if adverse < interval:
                return []

        # Build the entry
        units = (slot.index + 1) * layer.base_units
        new_price = tick.ask if direction == Direction.LONG else tick.bid

        # Reference for weighted avg: do not pass the current layer's R0.
        # weighted_avg_close_price already includes every live / pending slot
        # in this layer, so passing R0 again would double-count it.
        r0 = layer.slot_at(0)
        if r0 is not None and (r0.entry is not None or r0.pending_rebuild is not None):
            layer_ref = None
        elif head is not None:
            layer_ref = head
        else:
            layer_ref = None

        if cfg.counter_tp_mode == "weighted_avg":
            close_price, formula = layer.weighted_avg_close_price(
                new_price, units, include_ref=layer_ref
            )
        else:
            tp = counter_tp_pips(slot.index, cfg)
            if direction == Direction.LONG:
                close_price = new_price + tp * self.pip_size
            else:
                close_price = new_price - tp * self.pip_size
            op = "+" if direction == Direction.LONG else "-"
            formula = f"{new_price} {op} {tp} * {self.pip_size}"

        # Use the resolved head entry_id for root/parent references
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
            root_entry_id=head_entry_id,
            parent_entry_id=head_entry_id,
        )
        entry.expected_interval_pips = interval
        entry.actual_interval_pips = adverse
        entry.validation_status = "pass"

        # Compute stop-loss for this entry at creation time
        if cfg.stop_loss_enabled:
            next_interval = counter_interval_pips(slot.index + 1, cfg)
            if next_interval > 0:
                self._assign_stop_loss(entry, next_interval)

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
                + (f", SL={entry.stop_loss_price:.3f}" if entry.stop_loss_price is not None else "")
            ),
        )
        slot.fill(entry)

        # When a refillable slot is re-opened, unseal any higher-numbered
        # slots so the next adverse move can use them instead of jumping
        # to a new layer.
        layer.unseal_slots_above(slot.index)

        # Update close prices for non-weighted_avg modes
        if cfg.counter_tp_mode != "weighted_avg":
            for s in layer.slots:
                if s.index == 0 or s.entry is None or s.entry.is_hedge:
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
        """Open a layer-initial entry (R0) for a new layer."""
        cfg = self.config
        head = cycle.initial_entry
        head_entry_price, head_entry_id = cycle.effective_head()
        if head_entry_price is None:
            return []

        # Gate: head (or its SL snapshot) must be losing
        if head is not None:
            if (
                head.unrealised_loss_pips(
                    self._exit_side_price(head.direction, tick),
                    self.pip_size,
                )
                <= 0
            ):
                return []
        else:
            if cycle.direction == Direction.LONG:
                if (
                    head_entry_price - self._exit_side_price(cycle.direction, tick)
                ) / self.pip_size <= 0:
                    return []
            else:
                if (
                    self._exit_side_price(cycle.direction, tick) - head_entry_price
                ) / self.pip_size <= 0:
                    return []

        direction = cycle.direction
        prev_layer = cycle.current_layer
        assert prev_layer is not None
        new_layer_number = prev_layer.layer_number + 1
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
            root_entry_id=head_entry_id,
            parent_entry_id=head_entry_id,
        )

        close_price, formula = layer.layer_initial_close_price(
            price,
            abs(layer_entry.units),
            prev_layer,
            direction=direction,
            pip_size=self.pip_size,
            m_pips=cfg.m_pips,
        )

        layer_entry.close_price = close_price
        tp_pips = abs(close_price - layer_entry.entry_price) / self.pip_size
        layer_entry.expected_tp_pips = tp_pips
        layer_entry.validation_status = "pass"

        highest = prev_layer.highest_present_slot()
        if highest is not None:
            highest_price = (
                highest.entry.entry_price
                if highest.entry is not None
                else highest.pending_rebuild.entry_price
                if highest.pending_rebuild is not None
                else None
            )
            if highest_price is not None:
                layer_entry.actual_interval_pips = abs(highest_price - price) / self.pip_size

        # Compute stop-loss for this entry at creation time
        if cfg.stop_loss_enabled:
            next_interval = counter_interval_pips(1, cfg)
            if next_interval > 0:
                self._assign_stop_loss(layer_entry, next_interval)

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
                + (
                    f", SL={layer_entry.stop_loss_price:.3f}"
                    if layer_entry.stop_loss_price is not None
                    else ""
                )
            ),
        )
        # Place in R0 of the new layer
        slot0 = layer.slot_at(0)
        assert slot0 is not None  # noqa: S101
        slot0.fill(layer_entry)

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
        if not self.config.emergency_enabled:
            return None
        threshold = self.config.emergency_threshold
        if ratio < threshold:
            return None
        ss.protection_level = ProtectionLevel.EMERGENCY
        all_entries = ss.all_entries()
        logger.critical(
            "EMERGENCY STOP: margin ratio %.1f%% >= %s%% | NAV=%s, entries=%d",
            ratio,
            threshold,
            format_money(ss.account_nav),
            len(all_entries),
        )
        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_STOPPED,
            timestamp=tick.timestamp,
            data={
                "kind": "emergency_stop",
                "ratio": str(ratio),
                "threshold": str(threshold),
            },
        )
        event.strategy_type = "snowball"
        event.validation_status = "fail"
        return [event], (f"Emergency stop: margin ratio {ratio:.1f}% >= threshold {threshold}%")

    def _handle_lock(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> list[StrategyEvent] | None:
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
                                cycle=cycle,
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
        """Shrink: close positions from the front (oldest first) until ratio < m1_th."""
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
            entry, cycle = self._pick_shrink_target(ss, tick)
            if entry is None or cycle is None:
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
                    margin_ratio=ratio / Decimal("100"),
                    cycle=cycle,
                )
            )
            cycle.remove_entry(entry.entry_id)
            closed_count += 1

            # Approximate margin ratio after close
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

            # Mark any cycles emptied by shrink as completed.
            # Shrink also clears any pending rebuilds — if we're shrinking,
            # we don't want to rebuild stopped-out positions.
            for cycle in ss.active_cycles():
                if cycle.grid.is_empty():
                    # Clear pending rebuilds on the grid
                    for layer in cycle.grid.layers:
                        for slot in layer.slots:
                            slot.pending_rebuild = None
                    cycle.status = CycleStatus.COMPLETED
                    if cycle.realized_pnl < 0:
                        logger.warning(
                            "Cycle %d (%s) closed by shrink with negative realised P/L: %s",
                            cycle.cycle_id,
                            cycle.direction.value.upper(),
                            cycle.realized_pnl,
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
        candidate has the largest unrealised loss.
        Within a cycle: oldest position first (front of grid).
        """
        candidates: list[tuple[Entry, SnowballCycle, Decimal]] = []
        for cycle in ss.active_cycles():
            entry = cycle.grid.front_entry()
            if entry is not None:
                loss = entry.unrealised_loss_pips(tick.mid, self.pip_size)
                candidates.append((entry, cycle, loss))

        if not candidates:
            return None, None

        candidates.sort(key=lambda c: c[2], reverse=True)
        return candidates[0][0], candidates[0][1]

    # ------------------------------------------------------------------
    # Stop-loss protection
    # ------------------------------------------------------------------

    def _assign_stop_loss(
        self,
        entry: Entry,
        next_interval_pips: Decimal,
    ) -> None:
        """Compute and assign a stop-loss price to *entry* at creation time.

        The SL is derived from the hypothetical next entry's price, which is
        deterministic: ``entry_price ∓ next_interval_pips * pip_size``.

        Formula:
        - R0 entries use a one-interval stop so the distance to SL matches the
          distance from R0 to R1.
        - tp_pips = |close_price - entry_price| / pip_size
        - next_entry_price = entry_price - next_interval_pips * pip_size  (LONG)
                             entry_price + next_interval_pips * pip_size  (SHORT)
        - if tp_pips < next_interval_pips: SL = next_entry_price
        - else: SL = next_entry_price - next_interval_pips * pip_size  (LONG)
                     SL = next_entry_price + next_interval_pips * pip_size  (SHORT)
        """
        tp_pips = abs(entry.close_price - entry.entry_price) / self.pip_size
        if entry.is_long:
            next_entry_price = entry.entry_price - next_interval_pips * self.pip_size
            if entry.retracement_count == 0:
                sl = next_entry_price
            else:
                sl = stop_loss_price(tp_pips, next_entry_price, next_interval_pips, self.pip_size)
        else:
            next_entry_price = entry.entry_price + next_interval_pips * self.pip_size
            if entry.retracement_count == 0 or tp_pips < next_interval_pips:
                sl = next_entry_price
            else:
                sl = next_entry_price + next_interval_pips * self.pip_size
        entry.stop_loss_price = sl
        logger.debug(
            "SL assigned: entry_id=%d L%d/R%d, SL=%.5f (tp_pips=%.1f, next_interval=%.1f)",
            entry.entry_id,
            entry.layer_number,
            entry.retracement_count,
            sl,
            tp_pips,
            next_interval_pips,
        )

    def _is_stop_loss_temporarily_protected(self, layer: Layer, entry: Entry) -> bool:
        """Return True when the layer's highest live R should ignore stop-loss.

        Protection is dynamic per tick and per layer. Only the current
        highest occupied slot is eligible, and only when its R-number is at
        or above the configured threshold. R0 is never protected.
        """
        threshold = self.config.preserve_highest_r_from
        if threshold <= 0:
            return False

        highest = layer.highest_occupied_slot()
        if highest is None or highest.entry is None:
            return False
        if highest.index == 0 or highest.index < threshold:
            return False
        return highest.entry.entry_id == entry.entry_id

    def _process_stop_loss_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Close entries whose stop-loss price has been hit."""
        if not self.config.stop_loss_enabled:
            return []

        events: list[StrategyEvent] = []
        slots_to_close: list[tuple[Slot, Entry, Layer]] = []

        for layer in cycle.grid.layers:
            for slot in layer.slots:
                entry = slot.entry
                if entry is None or entry.stop_loss_price is None:
                    continue
                if entry.is_rebuild and self.config.disable_loss_cut_after_rebuild:
                    continue
                if entry.is_hedge:
                    continue
                if self._is_stop_loss_temporarily_protected(layer, entry):
                    continue

                hit = False
                if entry.is_long and tick.bid <= entry.stop_loss_price:
                    hit = True
                elif entry.is_short and tick.ask >= entry.stop_loss_price:
                    hit = True

                if hit:
                    slots_to_close.append((slot, entry, layer))

        for slot, entry, layer in slots_to_close:
            exit_price = entry.exit_price(tick)
            pips_lost = abs(exit_price - entry.entry_price) / self.pip_size

            logger.info(
                "Stop-loss hit (%s): L%d/R%d, entry=%.5f, SL=%.5f, exit=%.5f, -%.1f pips",
                entry.direction.value.upper(),
                entry.layer_number,
                entry.retracement_count,
                entry.entry_price,
                entry.stop_loss_price,
                exit_price,
                pips_lost,
            )

            # Close through the helper so lifecycle P/L is accumulated
            # consistently (the SL delta needs to flow into the slot's
            # running total and into the cycle total).
            close_event = self._close_entry(
                tick,
                entry,
                description=(
                    f"[PROTECTION] Stop-loss ({entry.direction.value.upper()}) | "
                    f"L{entry.layer_number}/R{entry.retracement_count}, "
                    f"entry={entry.entry_price:.5f}, SL={entry.stop_loss_price:.5f}, "
                    f"exit={exit_price:.5f}, -{pips_lost:.1f} pips"
                ),
                close_reason="stop_loss",
                validation_status="warn",
                cycle=cycle,
            )

            # Build the SL snapshot, carrying forward the slot's running
            # lifecycle P/L (including this SL loss) so a future rebuild
            # can continue the chain.
            entry.lifecycle_stop_loss_count += 1

            # Accumulate the deterministic price-unit drift between the
            # original entry price and this SL exit price so the rebuild
            # can tighten its TP by the same amount.  We always record
            # this drift; whether the rebuild actually uses it to shift
            # the TP is controlled by ``rebuild_price_adjustment_enabled``
            # at rebuild time.
            sl_price_drift = abs(exit_price - entry.entry_price)
            rebuild_price_offset = entry.rebuild_price_offset + sl_price_drift
            entry.rebuild_price_offset = rebuild_price_offset

            sl_snapshot = StopLossClosedEntry(
                entry_price=entry.entry_price,
                close_price=entry.close_price,
                units=entry.units,
                direction=entry.direction,
                role=entry.role,
                layer_number=entry.layer_number,
                retracement_count=entry.retracement_count,
                step=entry.step,
                root_entry_id=entry.root_entry_id,
                parent_entry_id=entry.parent_entry_id,
                cycle_id=cycle.cycle_id,
                position_id=entry.position_id,
                lifecycle_realized_pnl=entry.lifecycle_realized_pnl,
                lifecycle_stop_loss_count=entry.lifecycle_stop_loss_count,
                rebuild_price_offset=rebuild_price_offset,
            )
            slot.close_for_stop_loss(sl_snapshot)

            events.append(close_event)

        return events

    def _process_stop_loss_rebuilds(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]:
        """Rebuild positions that were closed by stop-loss when price returns.

        Iterates all slots in the cycle's grid that have ``pending_rebuild``
        set.  When the market price returns to the original entry price the
        position is re-opened in-place.
        """
        if not self.config.stop_loss_enabled:
            return []

        events: list[StrategyEvent] = []
        any_rebuilt = False

        # Convert buffer pips to price-unit offsets once.
        cfg = self.config
        apply_adjustment = cfg.rebuild_price_adjustment_enabled
        entry_buffer_price = cfg.rebuild_entry_price_buffer_pips * self.pip_size
        exit_buffer_price = cfg.rebuild_exit_price_buffer_pips * self.pip_size

        for layer in cycle.grid.layers:
            for slot in layer.slots:
                pending = slot.pending_rebuild
                if pending is None:
                    continue

                # Determine the rebuild trigger price: original entry
                # optionally tightened in the favourable direction by
                # ``rebuild_entry_price_buffer_pips`` when the adjustment
                # feature is enabled.
                if apply_adjustment and entry_buffer_price > 0:
                    if pending.direction == Direction.LONG:
                        trigger_price = pending.entry_price + entry_buffer_price
                    else:
                        trigger_price = pending.entry_price - entry_buffer_price
                else:
                    trigger_price = pending.entry_price

                # Check if price has returned to the trigger price
                hit = False
                if pending.direction == Direction.LONG and tick.bid >= trigger_price:
                    hit = True
                elif pending.direction == Direction.SHORT and tick.ask <= trigger_price:
                    hit = True

                if not hit:
                    continue

                # Compute the rebuild's take-profit so the slot's
                # lifecycle P/L can be fully recovered on TP.  Conceptually:
                #
                # The rebuild's profit on close (per unit) equals
                # ``|entry - new_close_price|`` (in quote-currency price
                # units).  The realised SL loss per unit accumulated on
                # this slot equals ``rebuild_price_offset`` (sum of
                # ``|sl_exit - entry|`` across all prior stop-losses).
                #
                # To keep the original TP whenever it already covers the
                # loss, and to extend it only when it doesn't, we use the
                # larger of the two distances.  The exit buffer is then
                # added on top in the favourable direction.  If the
                # feature is disabled, we fall back to the original TP.
                if apply_adjustment:
                    original_profit_distance = abs(pending.close_price - pending.entry_price)
                    required_profit_distance = (
                        max(original_profit_distance, pending.rebuild_price_offset)
                        + exit_buffer_price
                    )
                    if pending.direction == Direction.LONG:
                        adjusted_close_price = pending.entry_price + required_profit_distance
                    else:
                        adjusted_close_price = pending.entry_price - required_profit_distance

                    # Preserve the monotonic grid ordering that
                    # ``_validate_grid_ordering`` enforces: the rebuilt
                    # slot's TP must not cross the TP of the nearest
                    # present slot immediately above it in this layer.
                    # When the rebuild offset would push the TP past
                    # that bound, clamp it back so the grid stays
                    # ordered.  Loss recovery beyond the bound is
                    # sacrificed; stability of the overall grid wins.
                    upper_tp_bound = self._upper_neighbor_tp_bound(layer, slot.index)
                    if upper_tp_bound is not None:
                        if pending.direction == Direction.LONG:
                            if adjusted_close_price > upper_tp_bound:
                                logger.info(
                                    "Rebuild TP clamped to upper neighbor: "
                                    "L%d/R%d, pending_tp=%.5f, computed_adj=%.5f, clamped_to=%.5f",
                                    pending.layer_number,
                                    pending.retracement_count,
                                    pending.close_price,
                                    adjusted_close_price,
                                    upper_tp_bound,
                                )
                                adjusted_close_price = upper_tp_bound
                        else:
                            if adjusted_close_price < upper_tp_bound:
                                logger.info(
                                    "Rebuild TP clamped to upper neighbor: "
                                    "L%d/R%d, pending_tp=%.5f, computed_adj=%.5f, clamped_to=%.5f",
                                    pending.layer_number,
                                    pending.retracement_count,
                                    pending.close_price,
                                    adjusted_close_price,
                                    upper_tp_bound,
                                )
                                adjusted_close_price = upper_tp_bound
                else:
                    adjusted_close_price = pending.close_price

                # Rebuild the position with the adjusted parameters
                entry = Entry.open(
                    state=ss,
                    tick=tick,
                    direction=pending.direction,
                    units=pending.units,
                    step=pending.step,
                    close_price=adjusted_close_price,
                    role=pending.role,
                    layer_number=pending.layer_number,
                    retracement_count=pending.retracement_count,
                    root_entry_id=pending.root_entry_id,
                    parent_entry_id=pending.parent_entry_id,
                )
                # Override entry_price to the (optionally adjusted)
                # trigger price so downstream accounting uses the same
                # reference as the rebuild trigger.
                entry.entry_price = trigger_price
                entry.validation_status = "pass"
                entry.is_rebuild = True

                # Carry forward the slot's running lifecycle P/L, SL
                # count and accumulated price offset so any future
                # stop-loss → rebuild chain on this slot can keep
                # compounding the TP tightening.
                entry.lifecycle_realized_pnl = pending.lifecycle_realized_pnl
                entry.lifecycle_stop_loss_count = pending.lifecycle_stop_loss_count
                entry.rebuild_price_offset = pending.rebuild_price_offset

                # Optionally keep rebuilt positions exempt from further stop-loss closes.
                if self.config.stop_loss_enabled and not self.config.disable_loss_cut_after_rebuild:
                    next_interval = counter_interval_pips(
                        pending.retracement_count + 1, self.config
                    )
                    if next_interval > 0:
                        self._assign_stop_loss(entry, next_interval)

                slot.complete_rebuild(entry)

                adjustment_note = ""
                if apply_adjustment and (
                    adjusted_close_price != pending.close_price or entry_buffer_price > 0
                ):
                    adjustment_note = (
                        f", adj: entry {pending.entry_price:.5f}→{trigger_price:.5f}"
                        f", TP {pending.close_price:.5f}→{adjusted_close_price:.5f}"
                    )

                logger.info(
                    "Stop-loss rebuild (%s): L%d/R%d, entry=%.5f, TP=%.5f, units=%d%s",
                    pending.direction.value.upper(),
                    pending.layer_number,
                    pending.retracement_count,
                    trigger_price,
                    adjusted_close_price,
                    pending.units,
                    adjustment_note,
                )

                evt = entry.to_rebuild_event(
                    timestamp=tick.timestamp,
                    original_position_id=pending.position_id,
                    description=(
                        f"Stop-loss rebuild ({pending.direction.value.upper()}) | "
                        f"L{pending.layer_number}/R{pending.retracement_count}, "
                        f"units={pending.units}, TP={adjusted_close_price:.5f}"
                        + (
                            f", SL={entry.stop_loss_price:.3f}"
                            if entry.stop_loss_price is not None
                            else ""
                        )
                        + adjustment_note
                    ),
                )
                events.append(evt)
                any_rebuilt = True

        # If any entries were rebuilt and the cycle was pending, reactivate it.
        if any_rebuilt and cycle.is_pending:
            cycle.status = CycleStatus.ACTIVE
            logger.info(
                "Cycle %d (%s) reactivated after stop-loss rebuild",
                cycle.cycle_id,
                cycle.direction.value.upper(),
            )

        return events

    # ------------------------------------------------------------------
    # Core tick processing
    # ------------------------------------------------------------------

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        """Process a single tick."""
        self._grid_order_violation = None
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
                is_error=True,
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
            counter_close_events = self._process_cycle_counter_closes(ss, tick, cycle)
            events.extend(counter_close_events)

            events.extend(self._process_cycle_tp(ss, tick, cycle))

            if self._close_order_violation:
                state.strategy_state = ss.to_dict()
                return StrategyResult(
                    state=state,
                    events=events,
                    should_stop=True,
                    stop_reason=f"Close order violation: {self._close_order_violation}",
                    is_error=True,
                )

            # --- Stop-loss closes ---
            sl_close_events = self._process_stop_loss_closes(ss, tick, cycle)
            events.extend(sl_close_events)

            # --- Stop-loss rebuilds ---
            sl_rebuild_events = self._process_stop_loss_rebuilds(ss, tick, cycle)
            events.extend(sl_rebuild_events)

            if not counter_close_events:
                # Apply counter adds repeatedly within the same tick.
                # A single adverse move can cross multiple retracement
                # thresholds or even layer boundaries (for example when a
                # stop-loss hit sets the reference past the next counter
                # target).  Looping here closes that gap instead of waiting
                # for later ticks — during fast moves those follow-up ticks
                # often print retraces that would cancel the trigger.
                #
                # The loop is bounded by (f_max * (r_max + 1)) as a hard
                # safety rail against unexpected fixed points.
                max_iterations = max(1, self.config.f_max * (self.config.r_max + 1))
                for _ in range(max_iterations):
                    add_events = self._process_cycle_counter_adds(ss, tick, cycle)
                    if not add_events:
                        break
                    events.extend(add_events)

            self._validate_grid_ordering(cycle)
            if self._grid_order_violation:
                state.strategy_state = ss.to_dict()
                return StrategyResult(
                    state=state,
                    events=events,
                    should_stop=True,
                    stop_reason=f"Grid ordering violation: {self._grid_order_violation}",
                    is_error=True,
                )

            # --- Cycle status update ---
            # ACTIVE:    at least one open (live) entry exists.
            # PENDING:   no open entries, but at least one pending rebuild.
            # COMPLETED: no open entries and no pending rebuilds.
            if cycle.is_active or cycle.is_pending:
                has_open = not cycle.grid.is_empty()
                has_pending = cycle.grid.has_pending_rebuilds()
                if has_open:
                    if cycle.is_pending:
                        cycle.status = CycleStatus.ACTIVE
                elif has_pending:
                    if cycle.is_active:
                        cycle.status = CycleStatus.PENDING
                else:
                    cycle.status = CycleStatus.COMPLETED
                    if cycle.realized_pnl < 0:
                        logger.warning(
                            "Cycle %d (%s) completed with negative realised P/L: %s",
                            cycle.cycle_id,
                            cycle.direction.value.upper(),
                            cycle.realized_pnl,
                        )

        # --- Re-seed directions that have no tradable cycle ---
        # A direction needs a new cycle when:
        # 1. All cycles for that direction are COMPLETED, or
        # 2. reseed_on_all_pending is enabled and all remaining cycles
        #    are PENDING (no open positions, only pending rebuilds), or
        # 3. reseed_on_grid_exhausted is enabled and all remaining cycles
        #    have every slot in pending-rebuild state (grid fully saturated).
        active = ss.active_cycles()  # non-completed cycles
        for direction in (Direction.LONG, Direction.SHORT):
            if not self._hedging_enabled and direction == Direction.SHORT:
                continue
            dir_cycles = [c for c in active if c.direction == direction]
            if not dir_cycles:
                # No active or pending cycles — all completed.
                logger.info(
                    "No active %s cycle — creating new cycle",
                    direction.value.upper(),
                )
                new_events, _ = self._create_cycle(ss, tick, direction)
                events.extend(new_events)
            elif self.config.reseed_on_all_pending and all(c.is_pending for c in dir_cycles):
                # All cycles for this direction are PENDING (only pending
                # rebuilds, no open positions).  Start a fresh cycle.
                logger.info(
                    "All %s cycles pending — creating new cycle (reseed_on_all_pending)",
                    direction.value.upper(),
                )
                new_events, _ = self._create_cycle(ss, tick, direction)
                events.extend(new_events)
            elif self.config.reseed_on_grid_exhausted and all(
                c.is_grid_exhausted(self.config.f_max) for c in dir_cycles
            ):
                # All cycles have every slot in pending-rebuild state.
                logger.info(
                    "All %s cycle grids exhausted — creating new cycle (reseed_on_grid_exhausted)",
                    direction.value.upper(),
                )
                new_events, _ = self._create_cycle(ss, tick, direction)
                events.extend(new_events)

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
        """Apply order execution feedback (position IDs, cycle IDs) to state."""
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
            for layer in cycle.grid.layers:
                for slot in layer.slots:
                    if slot.entry is not None and slot.entry.entry_id == eid:
                        slot.entry.position_id = str(position_id)
                        self._sync_entry_fill_price(
                            entry=slot.entry,
                            layer=layer,
                            fill_price=binding.fill_price,
                        )
                        # Back-fill trade_cycle_id on the cycle when the
                        # initial entry (cycle_id == entry_id) is executed.
                        if (
                            binding.cycle_id
                            and cycle.cycle_id == eid
                            and cycle.trade_cycle_id is None
                        ):
                            cycle.trade_cycle_id = binding.cycle_id
            for entry in cycle.hedge_entries:
                if entry.entry_id == eid:
                    entry.position_id = str(position_id)
                    self._sync_entry_fill_price(
                        entry=entry,
                        layer=None,
                        fill_price=binding.fill_price,
                    )

        state.strategy_state = ss.to_dict()

    def _sync_entry_fill_price(
        self,
        *,
        entry: Entry,
        layer: Layer | None,
        fill_price: Decimal | None,
    ) -> None:
        """Align in-memory entry pricing with the broker fill price."""
        if fill_price is None:
            return

        fill_price = Decimal(str(fill_price))
        delta = fill_price - entry.entry_price
        if delta == 0:
            return

        entry.entry_price = fill_price

        if entry.stop_loss_price is not None:
            entry.stop_loss_price += delta

        if (
            layer is not None
            and entry.role == "counter"
            and self.config.counter_tp_mode == "weighted_avg"
        ):
            weighted = layer.current_weighted_avg_close_price()
            if weighted is not None:
                entry.close_price = weighted[0]
            return

        entry.close_price += delta
