"""Margin protection flow for the Snowball strategy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from logging import getLogger
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction, EventType
from apps.trading.events import ClosePositionEvent, GenericStrategyEvent, StrategyEvent
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.enums import CycleStatus, ProtectionLevel
from apps.trading.strategies.snowball.events import entry_open_event
from apps.trading.strategies.snowball.models import Entry, SnowballCycle, SnowballStrategyState
from apps.trading.utils import format_money, quote_to_account_rate

logger = getLogger(__name__)


class ProtectionStrategy(Protocol):
    config: SnowballStrategyConfig
    instrument: str
    account_currency: str
    pip_size: Decimal
    _close_order_violation: str | None

    def _close_entry(self, *args, **kwargs) -> ClosePositionEvent: ...


def margin_ratio(
    *,
    state: ExecutionState,
    ss: SnowballStrategyState,
    instrument: str,
    account_currency: str,
) -> Decimal:
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
    conv = quote_to_account_rate(instrument, mid, account_currency)
    required = mid * Decimal(str(total_units)) * Decimal("0.04") * conv
    return (required / nav) * Decimal("100")


def handle_emergency(
    *,
    strategy: ProtectionStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    ratio: Decimal,
) -> tuple[list[StrategyEvent], str] | None:
    if not strategy.config.emergency_enabled:
        return None
    threshold = strategy.config.emergency_threshold
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
        data={"kind": "emergency_stop", "ratio": str(ratio), "threshold": str(threshold)},
    )
    event.strategy_type = "snowball"
    event.validation_status = "fail"
    return [event], f"Emergency stop: margin ratio {ratio:.1f}% >= threshold {threshold}%"


def handle_lock(
    *,
    strategy: ProtectionStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    ratio: Decimal,
) -> list[StrategyEvent] | None:
    cfg = strategy.config
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

    logger.warning("LOCK MODE entered: margin ratio %.1f%% >= n_th=%.1f%%", ratio, cfg.n_th)

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
        target_cycle = next(
            (c for c in active if c.direction == hedge_dir), active[0] if active else None
        )
        if target_cycle is not None:
            target_cycle.hedge_entries.append(hedge_entry)
        ss.lock_hedge_ids.append(hedge_entry.entry_id)

        open_evt = entry_open_event(
            hedge_entry,
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


def handle_lock_release(
    *,
    strategy: ProtectionStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    ratio: Decimal,
) -> list[StrategyEvent]:
    if ss.protection_level != ProtectionLevel.LOCKED:
        return []
    cfg = strategy.config
    unlock_ok = ratio < cfg.m_th - Decimal("5")
    if ss.cooldown_until:
        cd = datetime.fromisoformat(ss.cooldown_until)
        if tick.timestamp < cd:
            unlock_ok = False
    if not unlock_ok:
        return []

    events: list[StrategyEvent] = []
    for hid in list(ss.lock_hedge_ids):
        for cycle in ss.cycles:
            for entry in list(cycle.hedge_entries):
                if entry.entry_id == hid:
                    events.append(
                        strategy._close_entry(
                            tick,
                            entry,
                            description=f"[PROTECTION] Lock hedge unwound | ratio={ratio:.1f}%",
                            close_reason="lock_hedge_neutralize",
                            validation_status="not_applicable",
                            cycle=cycle,
                        )
                    )
                    cycle.hedge_entries.remove(entry)
    ss.lock_hedge_ids = []
    ss.lock_entered_at = None
    ss.cooldown_until = None
    ss.protection_level = ProtectionLevel.SHRINK if ratio >= cfg.m_th else ProtectionLevel.NORMAL
    unlock_evt = GenericStrategyEvent(
        event_type=EventType.STATUS_CHANGED,
        timestamp=tick.timestamp,
        data={"kind": "snowball_unlocked", "ratio": str(ratio)},
    )
    unlock_evt.strategy_type = "snowball"
    unlock_evt.close_reason = "lock_released"
    events.append(unlock_evt)
    return events


def handle_shrink(
    *,
    strategy: ProtectionStrategy,
    state: ExecutionState,
    ss: SnowballStrategyState,
    tick: Tick,
    ratio: Decimal,
) -> list[StrategyEvent] | None:
    cfg = strategy.config
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
        entry, cycle = pick_shrink_target(ss, tick, strategy.pip_size)
        if entry is None or cycle is None:
            logger.error(
                "SHRINK EXHAUSTED: all positions closed but margin ratio "
                "%.1f%% still above m1_th=%.1f%%. Failing task.",
                ratio,
                cfg.m1_th,
            )
            strategy._close_order_violation = (
                f"Shrink exhausted: ratio={ratio:.1f}%, m1_th={cfg.m1_th}%, "
                f"no more positions to close"
            )
            break

        events.append(
            strategy._close_entry(
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
        ratio = margin_ratio(
            state=state,
            ss=ss,
            instrument=strategy.instrument,
            account_currency=strategy.account_currency,
        )

    if closed_count > 0:
        logger.warning(
            "SHRINK completed: closed %d position(s), ratio now %.1f%%", closed_count, ratio
        )
        for cycle in ss.active_cycles():
            if cycle.grid.is_empty():
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


def pick_shrink_target(
    ss: SnowballStrategyState,
    tick: Tick,
    pip_size: Decimal,
) -> tuple[Entry | None, SnowballCycle | None]:
    candidates: list[tuple[Entry, SnowballCycle, Decimal]] = []
    for cycle in ss.active_cycles():
        entry = cycle.grid.front_entry()
        if entry is not None:
            loss = entry.unrealised_loss_pips(tick.mid, pip_size)
            candidates.append((entry, cycle, loss))

    if not candidates:
        return None, None

    candidates.sort(key=lambda c: c[2], reverse=True)
    return candidates[0][0], candidates[0][1]
