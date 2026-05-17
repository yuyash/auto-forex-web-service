"""Margin protection service for the Snowball strategy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from logging import getLogger
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import EventType
from apps.trading.events import ClosePositionEvent, GenericStrategyEvent, StrategyEvent
from apps.trading.money import AccountCurrency
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.enums import CycleStatus, ProtectionLevel
from apps.trading.strategies.snowball.cycle_state import SnowballCycle, SnowballStrategyState
from apps.trading.strategies.snowball.entries import Entry
from apps.trading.utils import Instrument, format_money

logger = getLogger(__name__)


class ProtectionStrategy(Protocol):
    config: SnowballStrategyConfig
    instrument: str
    account_currency: str
    pip_size: Decimal


@dataclass(frozen=True)
class ShrinkResult:
    events: list[StrategyEvent]
    close_order_violation: str | None = None


class SnowballProtectionService:
    """Own Snowball margin-protection decisions and state transitions."""

    def margin_ratio(
        self,
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
        conv = Instrument(instrument).quote_to_account_rate(mid, AccountCurrency(account_currency))
        required = mid * Decimal(str(total_units)) * Decimal("0.04") * conv
        return (required / nav) * Decimal("100")

    def handle_emergency(
        self,
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

    def handle_shrink(
        self,
        *,
        strategy: ProtectionStrategy,
        close_entry: Callable[..., ClosePositionEvent],
        state: ExecutionState,
        ss: SnowballStrategyState,
        tick: Tick,
        ratio: Decimal,
    ) -> ShrinkResult | None:
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
            entry, cycle = self.pick_shrink_target(ss, tick, strategy.pip_size)
            if entry is None or cycle is None:
                logger.error(
                    "SHRINK EXHAUSTED: all positions closed but margin ratio "
                    "%.1f%% still above m1_th=%.1f%%. Failing task.",
                    ratio,
                    cfg.m1_th,
                )
                close_order_violation = (
                    f"Shrink exhausted: ratio={ratio:.1f}%, m1_th={cfg.m1_th}%, "
                    f"no more positions to close"
                )
                return ShrinkResult(events=events, close_order_violation=close_order_violation)

            events.append(
                close_entry(
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
            ratio = self.margin_ratio(
                state=state,
                ss=ss,
                instrument=strategy.instrument,
                account_currency=strategy.account_currency,
            )

        if closed_count > 0:
            logger.warning(
                "SHRINK completed: closed %d position(s), ratio now %.1f%%",
                closed_count,
                ratio,
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
        return ShrinkResult(events=events)

    def pick_shrink_target(
        self,
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


SNOWBALL_PROTECTION = SnowballProtectionService()
