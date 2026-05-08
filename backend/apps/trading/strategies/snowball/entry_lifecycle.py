"""Entry lifecycle event helpers for Snowball strategy."""

from __future__ import annotations

from decimal import Decimal
from logging import Logger
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.events import ClosePositionEvent
from apps.trading.strategies.snowball.events import SNOWBALL_EVENTS
from apps.trading.strategies.snowball.models import Entry, SnowballCycle
from apps.trading.utils import format_money


class EntryLifecycleStrategy(Protocol):
    instrument: str
    pip_size: Decimal
    account_currency: str


def close_entry(
    strategy: EntryLifecycleStrategy,
    logger: Logger,
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
    """Create a close event and update slot/cycle realised P/L accounting."""
    event = SNOWBALL_EVENTS.entry_close_event(
        entry,
        tick,
        instrument=strategy.instrument,
        pip_size=strategy.pip_size,
        account_currency=strategy.account_currency,
        description=description,
        close_reason=close_reason,
        actual_tp_pips=actual_tp_pips,
        validation_status=validation_status,
    )
    if margin_ratio is not None:
        event.margin_ratio = margin_ratio

    delta_pnl = event.pnl
    entry.lifecycle_realized_pnl += delta_pnl
    if cycle is not None:
        cycle.realized_pnl += delta_pnl

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
