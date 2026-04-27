"""Counter-entry open/close flow for the Snowball strategy."""

from __future__ import annotations

from decimal import Decimal
from logging import getLogger
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.events import StrategyEvent
from apps.trading.strategies.snowball.calculators import (
    counter_interval_pips,
    counter_tp_pips,
)
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.events import entry_open_event
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    Slot,
    SnowballCycle,
    SnowballStrategyState,
)
from apps.trading.strategies.snowball.pricing import weighted_avg_close_price

logger = getLogger(__name__)


class CounterFlowStrategy(Protocol):
    config: SnowballStrategyConfig
    pip_size: Decimal

    def _close_entry(self, *args, **kwargs): ...

    def _open_layer_initial(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]: ...

    def _assign_configured_stop_loss(self, entry: Entry, slot_number: int) -> None: ...


def process_cycle_counter_closes(
    strategy: CounterFlowStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    cycle: SnowballCycle,
) -> list[StrategyEvent]:
    """Close counter entries from the back (newest first)."""
    if cycle.completed:
        return []

    events: list[StrategyEvent] = []
    while True:
        closed_this_pass = False
        for layer in reversed(list(cycle.grid.layers)):
            highest = layer.highest_occupied_slot()
            if highest is None or highest.entry is None:
                continue

            entry = highest.entry
            if entry.layer_number == 1 and entry.retracement_count == 0:
                continue
            if not entry_take_profit_hit(entry, tick):
                continue

            exit_price = entry.exit_price(tick)
            pips_gained = abs(exit_price - entry.entry_price) / strategy.pip_size

            logger.info(
                "Counter TP (%s): L%s/R%s, +%.1f pips",
                entry.direction.value.upper(),
                entry.layer_number,
                entry.retracement_count,
                pips_gained,
            )
            layer.close_slot(highest.index)
            cycle.counter_close_count += 1
            events.append(
                strategy._close_entry(
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
            )

            if layer.layer_number > 1:
                _close_layer_initial_if_ready(strategy, tick, cycle, layer, events)
                if not layer.has_open_entries():
                    cycle.grid.layers.remove(layer)

            closed_this_pass = True
            break

        if not closed_this_pass:
            return events


def _close_layer_initial_if_ready(
    strategy: CounterFlowStrategy,
    tick: Tick,
    cycle: SnowballCycle,
    layer: Layer,
    events: list[StrategyEvent],
) -> None:
    remaining = layer.occupied_slots()
    if len(remaining) != 1 or remaining[0].index != 0:
        return
    r0_entry = remaining[0].entry
    if r0_entry is None or not entry_take_profit_hit(r0_entry, tick):
        return

    r0_exit = r0_entry.exit_price(tick)
    r0_pips = abs(r0_exit - r0_entry.entry_price) / strategy.pip_size
    logger.info(
        "Layer initial TP (%s): L%s, +%.1f pips; removing layer",
        r0_entry.direction.value.upper(),
        layer.layer_number,
        r0_pips,
    )
    layer.close_slot(0, refillable=False)
    events.append(
        strategy._close_entry(
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


def entry_take_profit_hit(entry: Entry, tick: Tick) -> bool:
    if entry.close_price <= 0:
        return False
    if entry.is_long:
        return tick.bid >= entry.close_price
    return tick.ask <= entry.close_price


def process_cycle_counter_adds(
    strategy: CounterFlowStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    cycle: SnowballCycle,
) -> list[StrategyEvent]:
    """Add a new counter entry if adverse distance threshold is met."""
    if cycle.completed:
        return []
    cfg = strategy.config
    layer = cycle.current_layer
    if layer is None:
        return []

    head = cycle.initial_entry
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

    def head_losing() -> bool:
        if head is not None:
            return head.unrealised_loss_pips(
                _exit_side_price(head.direction, tick),
                strategy.pip_size,
            ) > Decimal("0")
        if head_entry_price is None:
            return False
        if head_direction == Direction.LONG:
            return (
                head_entry_price - _exit_side_price(head_direction, tick)
            ) / strategy.pip_size > Decimal("0")
        return (
            _exit_side_price(head_direction, tick) - head_entry_price
        ) / strategy.pip_size > Decimal("0")

    if layer.needs_new_layer:
        if cycle.layer_count >= cfg.f_max or not head_losing():
            return []
        if not _new_layer_interval_hit(strategy, tick, cycle, layer):
            return []
        return strategy._open_layer_initial(ss, tick, cycle)

    slot = layer.next_available_counter_slot()
    if slot is None or not head_losing():
        return []

    adverse_interval = _counter_slot_adverse_interval(
        strategy,
        tick,
        cycle,
        layer,
        slot,
        head_entry_price,
    )
    if adverse_interval is None:
        return []
    adverse, interval = adverse_interval
    if adverse < interval:
        return []

    return _open_counter_entry(
        strategy,
        ss,
        tick,
        cycle,
        layer,
        slot,
        adverse,
        interval,
        head,
        head_entry_id,
    )


def _new_layer_interval_hit(
    strategy: CounterFlowStrategy,
    tick: Tick,
    cycle: SnowballCycle,
    layer: Layer,
) -> bool:
    highest = layer.highest_present_slot()
    if highest is None:
        return True
    ref_price = _slot_reference_price(highest)
    if ref_price is None:
        return True

    direction = cycle.direction
    fresh_same_tick = highest.entry is not None and highest.entry.opened_at == tick.timestamp
    if fresh_same_tick:
        r0_ref_price = _layer_r0_reference_price(layer)
        if r0_ref_price is None:
            return True
        cumulative_interval = Decimal("0")
        for k in range(1, highest.index + 2):
            cumulative_interval += counter_interval_pips(k, strategy.config)
        current_entry_price = _entry_side_price(direction, tick)
        adverse = _adverse_pips(direction, r0_ref_price, current_entry_price, strategy.pip_size)
        return adverse >= cumulative_interval

    current_entry_price = _entry_side_price(direction, tick)
    adverse = _adverse_pips(direction, ref_price, current_entry_price, strategy.pip_size)
    interval = counter_interval_pips(highest.index + 1, strategy.config)
    return adverse >= interval


def _counter_slot_adverse_interval(
    strategy: CounterFlowStrategy,
    tick: Tick,
    cycle: SnowballCycle,
    layer: Layer,
    slot: Slot,
    head_entry_price: Decimal | None,
) -> tuple[Decimal, Decimal] | None:
    direction = cycle.direction
    current_entry_price = _entry_side_price(direction, tick)
    previous_slot = layer.previous_present_slot(slot.index)
    fresh_same_tick = (
        previous_slot is not None
        and previous_slot.entry is not None
        and previous_slot.entry.opened_at == tick.timestamp
        and previous_slot.entry.entry_price == current_entry_price
    )

    if fresh_same_tick:
        r0_ref_price = _layer_r0_reference_price(layer) or head_entry_price
        if r0_ref_price is None:
            return None
        cumulative_interval = Decimal("0")
        for k in range(1, slot.index + 1):
            cumulative_interval += counter_interval_pips(k, strategy.config)
        adverse = _adverse_pips(direction, r0_ref_price, current_entry_price, strategy.pip_size)
        return adverse, cumulative_interval

    if previous_slot is not None:
        ref_price = _slot_reference_price(previous_slot)
    else:
        ref_price = _layer_r0_reference_price(layer) or head_entry_price
    if ref_price is None:
        return None
    adverse = _adverse_pips(direction, ref_price, current_entry_price, strategy.pip_size)
    interval = counter_interval_pips(slot.index, strategy.config)
    return adverse, interval


def _open_counter_entry(
    strategy: CounterFlowStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    cycle: SnowballCycle,
    layer: Layer,
    slot: Slot,
    adverse: Decimal,
    interval: Decimal,
    head: Entry | None,
    head_entry_id: int | None,
) -> list[StrategyEvent]:
    cfg = strategy.config
    direction = cycle.direction
    units = (slot.index + 1) * layer.base_units
    new_price = _entry_side_price(direction, tick)

    r0 = layer.slot_at(0)
    if r0 is not None and (r0.entry is not None or r0.pending_rebuild is not None):
        layer_ref = None
    elif head is not None:
        layer_ref = head
    else:
        layer_ref = None

    if cfg.counter_tp_mode == "weighted_avg":
        close_price, formula = weighted_avg_close_price(
            layer,
            new_price=new_price,
            new_units=units,
            include_ref=layer_ref,
        )
    else:
        tp = counter_tp_pips(slot.index, cfg)
        if direction == Direction.LONG:
            close_price = new_price + tp * strategy.pip_size
        else:
            close_price = new_price - tp * strategy.pip_size
        op = "+" if direction == Direction.LONG else "-"
        formula = f"{new_price} {op} {tp} * {strategy.pip_size}"

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

    if cfg.stop_loss_enabled:
        strategy._assign_configured_stop_loss(entry, slot.index + 1)

    logger.info(
        "Counter add (%s) in cycle %d: L%d/R%d, units=%d, adverse=%.1f pips",
        direction.value.upper(),
        cycle.cycle_id,
        layer.layer_number,
        slot.index,
        units,
        adverse,
    )

    evt = entry_open_event(
        entry,
        timestamp=tick.timestamp,
        planned_exit_price_formula=formula,
        description=format_counter_add_description(
            direction=direction,
            layer=layer,
            slot=slot,
            units=units,
            adverse=adverse,
            close_price=close_price,
            stop_loss_price=entry.stop_loss_price,
        ),
    )
    slot.fill(entry)
    layer.unseal_slots_above(slot.index)

    if cfg.counter_tp_mode != "weighted_avg":
        _sync_step_counter_take_profits(strategy, direction, layer)

    return [evt]


def _sync_step_counter_take_profits(
    strategy: CounterFlowStrategy,
    direction: Direction,
    layer: Layer,
) -> None:
    for slot in layer.slots:
        if slot.index == 0 or slot.entry is None or slot.entry.is_hedge:
            continue
        step_tp = counter_tp_pips(slot.index, strategy.config)
        if direction == Direction.LONG:
            slot.entry.close_price = slot.entry.entry_price + step_tp * strategy.pip_size
        else:
            slot.entry.close_price = slot.entry.entry_price - step_tp * strategy.pip_size


def format_counter_add_description(
    *,
    direction: Direction,
    layer: Layer,
    slot: Slot,
    units: int,
    adverse: Decimal,
    close_price: Decimal,
    stop_loss_price: Decimal | None,
) -> str:
    description = (
        f"Counter add ({direction.value.upper()}) | "
        f"L{layer.layer_number}/R{slot.index}, units={units}, "
        f"adverse={adverse:.1f} pips, TP={close_price:.3f}"
    )
    if stop_loss_price is not None:
        description += f", SL={stop_loss_price:.3f}"
    return description


def _entry_side_price(direction: Direction, tick: Tick) -> Decimal:
    return tick.ask if direction == Direction.LONG else tick.bid


def _exit_side_price(direction: Direction, tick: Tick) -> Decimal:
    return tick.bid if direction == Direction.LONG else tick.ask


def _slot_reference_price(slot: Slot) -> Decimal | None:
    if slot.entry is not None:
        return slot.entry.entry_price
    if slot.pending_rebuild is not None:
        return slot.pending_rebuild.entry_price
    return None


def _layer_r0_reference_price(layer: Layer) -> Decimal | None:
    r0 = layer.slot_at(0)
    if r0 is None:
        return None
    return _slot_reference_price(r0)


def _adverse_pips(
    direction: Direction,
    ref_price: Decimal,
    current_entry_price: Decimal,
    pip_size: Decimal,
) -> Decimal:
    if direction == Direction.LONG:
        return (ref_price - current_entry_price) / pip_size
    return (current_entry_price - ref_price) / pip_size
