"""Account metric updates for the Snowball strategy."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from apps.trading.dataclasses.tick import Tick
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.snowball.models import SnowballStrategyState
from apps.trading.strategies.snowball.protection import margin_ratio
from apps.trading.utils import AccountCurrency, Instrument


def update_account_metrics(
    *,
    state: ExecutionState,
    ss: SnowballStrategyState,
    tick: Tick,
    instrument: str,
    account_currency: str,
    margin_ratio_func: Callable[..., Decimal] = margin_ratio,
) -> Decimal:
    """Refresh NAV and margin-ratio metrics from current tick/account state."""
    if state.current_balance:
        ss.account_balance = Decimal(str(state.current_balance))

    unrealized = Decimal("0")
    conversion_rate = Instrument(instrument).quote_to_account_rate(
        tick.mid,
        AccountCurrency(account_currency),
    )
    for entry in ss.all_entries():
        if entry.is_long:
            unrealized += (
                (tick.bid - entry.entry_price) * Decimal(str(entry.units)) * conversion_rate
            )
        else:
            unrealized += (
                (entry.entry_price - tick.ask) * Decimal(str(entry.units)) * conversion_rate
            )

    ss.account_nav = ss.account_balance + unrealized
    if ss.account_nav <= 0:
        ss.account_nav = ss.account_balance

    ratio = margin_ratio_func(
        state=state,
        ss=ss,
        instrument=instrument,
        account_currency=account_currency,
    )
    ss.metrics["margin_ratio"] = str(ratio / Decimal("100"))
    return ratio
