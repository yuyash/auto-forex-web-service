"""Stop-loss close and rebuild flow for the Snowball strategy."""

from __future__ import annotations

from decimal import Decimal
from logging import getLogger
from collections.abc import Callable
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.events import StrategyEvent
from apps.trading.strategies.snowball.calculators import SnowballCalculator, round_to_step
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.enums import CycleStatus
from apps.trading.strategies.snowball.events import entry_rebuild_event
from apps.trading.strategies.snowball.grid_policy import (
    grid_tp_bounds,
    preceding_entry_bound,
    propagate_pending_rebuild_tp,
)
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    Slot,
    SnowballCycle,
    SnowballStrategyState,
    StopLossClosedEntry,
)
from apps.trading.strategies.snowball.pricing import rebuild_take_profit_price

logger = getLogger(__name__)


class StopLossFlowStrategy(Protocol):
    config: SnowballStrategyConfig
    pip_size: Decimal
    calculator: SnowballCalculator


def _calculator(strategy: StopLossFlowStrategy) -> SnowballCalculator:
    calculator = getattr(strategy, "calculator", None)
    if isinstance(calculator, SnowballCalculator):
        return calculator
    return SnowballCalculator(strategy.config)


def assign_stop_loss(
    strategy: StopLossFlowStrategy,
    entry: Entry,
    sl_pips: Decimal,
) -> None:
    """Compute and assign a stop-loss price to an entry."""
    if sl_pips <= 0:
        return
    if entry.is_long:
        sl = entry.entry_price - sl_pips * strategy.pip_size
    else:
        sl = entry.entry_price + sl_pips * strategy.pip_size
    entry.stop_loss_price = sl
    logger.debug(
        "SL assigned: entry_id=%d L%d/R%d, SL=%.5f (sl_pips=%.1f)",
        entry.entry_id,
        entry.layer_number,
        entry.retracement_count,
        sl,
        sl_pips,
    )


def assign_auto_stop_loss(
    strategy: StopLossFlowStrategy,
    entry: Entry,
    next_interval_pips: Decimal,
) -> None:
    """Apply interval-based stop-loss placement."""
    tp_pips = abs(entry.close_price - entry.entry_price) / strategy.pip_size
    if entry.is_long:
        next_entry_price = entry.entry_price - next_interval_pips * strategy.pip_size
        if entry.retracement_count == 0 or tp_pips < next_interval_pips:
            sl = next_entry_price
        else:
            sl = next_entry_price - next_interval_pips * strategy.pip_size
    else:
        next_entry_price = entry.entry_price + next_interval_pips * strategy.pip_size
        if entry.retracement_count == 0 or tp_pips < next_interval_pips:
            sl = next_entry_price
        else:
            sl = next_entry_price + next_interval_pips * strategy.pip_size
    entry.stop_loss_price = sl
    logger.debug(
        "Auto SL assigned: entry_id=%d L%d/R%d, SL=%.5f (tp_pips=%.1f, next_interval=%.1f)",
        entry.entry_id,
        entry.layer_number,
        entry.retracement_count,
        sl,
        tp_pips,
        next_interval_pips,
    )


def assign_configured_stop_loss(
    strategy: StopLossFlowStrategy,
    entry: Entry,
    slot_number: int,
) -> None:
    """Assign stop-loss using the configured mode for a 1-based slot number."""
    if strategy.config.stop_loss_mode == "auto":
        next_interval = _calculator(strategy).counter_interval_pips(slot_number)
        if next_interval > 0:
            assign_auto_stop_loss(strategy, entry, next_interval)
        return

    sl_pips = _calculator(strategy).stop_loss_pips(slot_number)
    if sl_pips > 0:
        assign_stop_loss(strategy, entry, sl_pips)


def assign_rebuild_stop_loss(
    strategy: StopLossFlowStrategy,
    entry: Entry,
    pending: StopLossClosedEntry,
) -> None:
    """Assign stop-loss to a rebuilt entry using rebuild-specific settings."""
    if not strategy.config.stop_loss_enabled or strategy.config.disable_loss_cut_after_rebuild:
        return

    if strategy.config.rebuild_stop_loss_mode == "same":
        if pending.stop_loss_price is not None:
            entry.stop_loss_price = pending.stop_loss_price
        return

    values = strategy.config.rebuild_stop_loss_manual_pips
    if not values:
        return
    idx = min(max(pending.retracement_count, 0), len(values) - 1)
    sl_pips = round_to_step(values[idx], strategy.config.round_step_pips)
    if sl_pips > 0:
        assign_stop_loss(strategy, entry, sl_pips)


def is_stop_loss_temporarily_protected(
    config: SnowballStrategyConfig,
    layer: Layer,
    entry: Entry,
) -> bool:
    """Return True when the layer's highest live R should ignore stop-loss."""
    if not config.preserve_highest_retracement_enabled:
        return False
    threshold = config.preserve_highest_r_from
    highest = layer.highest_occupied_slot()
    if highest is None or highest.entry is None:
        return False
    if highest.index == 0 or highest.index < threshold:
        return False
    return highest.entry.entry_id == entry.entry_id


def process_stop_loss_closes(
    strategy: StopLossFlowStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    cycle: SnowballCycle,
    *,
    close_entry: Callable[..., StrategyEvent],
) -> list[StrategyEvent]:
    """Close entries whose stop-loss price has been hit."""
    if not strategy.config.stop_loss_enabled:
        return []

    events: list[StrategyEvent] = []
    slots_to_close: list[tuple[Slot, Entry, Layer]] = []

    for layer in cycle.grid.layers:
        for slot in layer.slots:
            entry = slot.entry
            if entry is None or entry.stop_loss_price is None:
                continue
            if entry.is_rebuild and strategy.config.disable_loss_cut_after_rebuild:
                continue
            if entry.is_hedge:
                continue
            if is_stop_loss_temporarily_protected(strategy.config, layer, entry):
                continue
            if _stop_loss_hit(entry, tick):
                slots_to_close.append((slot, entry, layer))

    for slot, entry, _layer in slots_to_close:
        exit_price = entry.exit_price(tick)
        pips_lost = abs(exit_price - entry.entry_price) / strategy.pip_size

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

        close_event = close_entry(
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

        entry.lifecycle_stop_loss_count += 1
        if strategy.config.rebuild_enabled:
            slot.close_for_stop_loss(_stop_loss_snapshot(entry, cycle, pips_lost))
        else:
            slot.close(refillable=False)

        events.append(close_event)

    return events


def process_stop_loss_rebuilds(
    strategy: StopLossFlowStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    cycle: SnowballCycle,
) -> list[StrategyEvent]:
    """Rebuild positions that were closed by stop-loss when price returns."""
    if not strategy.config.stop_loss_enabled or not strategy.config.rebuild_enabled:
        return []

    events: list[StrategyEvent] = []
    any_rebuilt = False
    cfg = strategy.config
    apply_adjustment = (
        cfg.rebuild_price_adjustment_enabled and cfg.rebuild_take_profit_mode == "same"
    )
    entry_buffer_price = cfg.rebuild_entry_price_buffer_pips * strategy.pip_size
    exit_buffer_price = cfg.rebuild_exit_price_buffer_pips * strategy.pip_size

    for layer in cycle.grid.layers:
        for slot in layer.slots:
            pending = slot.pending_rebuild
            if pending is None:
                continue

            trigger_price = _rebuild_trigger_price(pending, apply_adjustment, entry_buffer_price)
            trigger_price = _clamp_rebuild_entry_price(cycle, layer, slot, pending, trigger_price)
            if not _rebuild_trigger_hit(pending, tick, trigger_price):
                continue

            adjusted_close_price = rebuild_take_profit_price(
                pending=pending,
                entry_price=trigger_price,
                pip_size=strategy.pip_size,
                config=cfg,
            )
            if apply_adjustment and exit_buffer_price > 0:
                if pending.direction == Direction.LONG:
                    adjusted_close_price += exit_buffer_price
                else:
                    adjusted_close_price -= exit_buffer_price
            adjusted_close_price = _clamp_rebuild_take_profit(
                cycle,
                layer,
                slot,
                pending,
                adjusted_close_price,
            )
            _propagate_rebuild_take_profit(cycle, layer, slot, pending, adjusted_close_price)

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
            entry.entry_price = trigger_price
            entry.validation_status = "pass"
            entry.is_rebuild = True
            entry.lifecycle_realized_pnl = pending.lifecycle_realized_pnl
            entry.lifecycle_stop_loss_count = pending.lifecycle_stop_loss_count

            assign_rebuild_stop_loss(strategy, entry, pending)
            slot.complete_rebuild(entry)

            adjustment_note = ""
            if adjusted_close_price != pending.close_price or (
                apply_adjustment and entry_buffer_price > 0
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

            events.append(
                entry_rebuild_event(
                    entry,
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
            )
            any_rebuilt = True

    if any_rebuilt and cycle.is_pending:
        cycle.status = CycleStatus.ACTIVE
        logger.info(
            "Cycle %d (%s) reactivated after stop-loss rebuild",
            cycle.cycle_id,
            cycle.direction.value.upper(),
        )

    return events


def _stop_loss_hit(entry: Entry, tick: Tick) -> bool:
    stop_loss_price = entry.stop_loss_price
    if stop_loss_price is None:
        return False
    return bool(
        (entry.is_long and tick.bid <= stop_loss_price)
        or (entry.is_short and tick.ask >= stop_loss_price)
    )


def _stop_loss_snapshot(
    entry: Entry,
    cycle: SnowballCycle,
    pips_lost: Decimal,
) -> StopLossClosedEntry:
    return StopLossClosedEntry(
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
        stop_loss_price=entry.stop_loss_price,
        lifecycle_realized_pnl=entry.lifecycle_realized_pnl,
        lifecycle_stop_loss_count=entry.lifecycle_stop_loss_count,
        stop_loss_loss_pips=pips_lost,
    )


def _rebuild_trigger_price(
    pending: StopLossClosedEntry,
    apply_adjustment: bool,
    entry_buffer_price: Decimal,
) -> Decimal:
    if not apply_adjustment or entry_buffer_price <= 0:
        return pending.entry_price
    if pending.direction == Direction.LONG:
        return pending.entry_price + entry_buffer_price
    return pending.entry_price - entry_buffer_price


def _clamp_rebuild_entry_price(
    cycle: SnowballCycle,
    layer: Layer,
    slot: Slot,
    pending: StopLossClosedEntry,
    trigger_price: Decimal,
) -> Decimal:
    entry_bound = preceding_entry_bound(cycle, layer, slot.index)
    if entry_bound is None:
        return trigger_price
    if pending.direction == Direction.LONG and trigger_price > entry_bound:
        logger.info(
            "Rebuild entry clamped to preserve grid ordering: "
            "L%d/R%d, trigger=%.5f, bound=%.5f, clamped_to=%.5f",
            pending.layer_number,
            pending.retracement_count,
            trigger_price,
            entry_bound,
            entry_bound,
        )
        return entry_bound
    if pending.direction == Direction.SHORT and trigger_price < entry_bound:
        logger.info(
            "Rebuild entry clamped to preserve grid ordering: "
            "L%d/R%d, trigger=%.5f, bound=%.5f, clamped_to=%.5f",
            pending.layer_number,
            pending.retracement_count,
            trigger_price,
            entry_bound,
            entry_bound,
        )
        return entry_bound
    return trigger_price


def _rebuild_trigger_hit(
    pending: StopLossClosedEntry,
    tick: Tick,
    trigger_price: Decimal,
) -> bool:
    if pending.direction == Direction.LONG:
        return tick.bid >= trigger_price
    return tick.ask <= trigger_price


def _clamp_rebuild_take_profit(
    cycle: SnowballCycle,
    layer: Layer,
    slot: Slot,
    pending: StopLossClosedEntry,
    adjusted_close_price: Decimal,
) -> Decimal:
    hard_bound, _soft_bound = grid_tp_bounds(cycle, layer, slot.index)
    if hard_bound is None:
        return adjusted_close_price
    if pending.direction == Direction.LONG and adjusted_close_price > hard_bound:
        logger.info(
            "Rebuild TP clamped to upper neighbor: "
            "L%d/R%d, pending_tp=%.5f, computed_adj=%.5f, clamped_to=%.5f",
            pending.layer_number,
            pending.retracement_count,
            pending.close_price,
            adjusted_close_price,
            hard_bound,
        )
        return hard_bound
    if pending.direction == Direction.SHORT and adjusted_close_price < hard_bound:
        logger.info(
            "Rebuild TP clamped to upper neighbor: "
            "L%d/R%d, pending_tp=%.5f, computed_adj=%.5f, clamped_to=%.5f",
            pending.layer_number,
            pending.retracement_count,
            pending.close_price,
            adjusted_close_price,
            hard_bound,
        )
        return hard_bound
    return adjusted_close_price


def _propagate_rebuild_take_profit(
    cycle: SnowballCycle,
    layer: Layer,
    slot: Slot,
    pending: StopLossClosedEntry,
    adjusted_close_price: Decimal,
) -> None:
    propagated = propagate_pending_rebuild_tp(cycle, layer, slot.index, adjusted_close_price)
    for lno, sidx, old_tp, new_tp in propagated:
        logger.info(
            "Pending-rebuild TP extended to preserve ordering: "
            "L%d/R%d, old_tp=%.5f, new_tp=%.5f "
            "(triggered by L%d/R%d rebuild @ TP=%.5f)",
            lno,
            sidx,
            old_tp,
            new_tp,
            pending.layer_number,
            pending.retracement_count,
            adjusted_close_price,
        )
