"""Account metric updates for the Snowball strategy."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from apps.trading.dataclasses.tick import Tick
from apps.trading.money import AccountCurrency
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState
from apps.trading.strategies.snowball.protection import SNOWBALL_PROTECTION
from apps.trading.utils import Instrument


class SnowballAccountMetricsUpdater:
    """Refresh NAV and margin-ratio metrics from current tick/account state."""

    def __init__(
        self,
        *,
        margin_ratio_func: Callable[..., Decimal] | None = None,
    ) -> None:
        self.margin_ratio_func = margin_ratio_func

    def update(
        self,
        *,
        state: ExecutionState,
        ss: SnowballStrategyState,
        tick: Tick,
        instrument: str,
        account_currency: str,
    ) -> Decimal:
        """Update account metrics and return the current margin ratio percentage."""
        if state.current_balance:
            ss.account_balance = Decimal(str(state.current_balance))

        ss.account_nav = ss.account_balance + self._unrealized_pnl(
            ss=ss,
            tick=tick,
            instrument=instrument,
            account_currency=account_currency,
        )
        if ss.account_nav <= 0:
            ss.account_nav = ss.account_balance

        ratio = self._margin_ratio_func()(
            state=state,
            ss=ss,
            instrument=instrument,
            account_currency=account_currency,
        )
        ss.metrics["margin_ratio"] = str(ratio / Decimal("100"))
        return ratio

    def _margin_ratio_func(self) -> Callable[..., Decimal]:
        return self.margin_ratio_func or SNOWBALL_PROTECTION.margin_ratio

    def _unrealized_pnl(
        self,
        *,
        ss: SnowballStrategyState,
        tick: Tick,
        instrument: str,
        account_currency: str,
    ) -> Decimal:
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
        return unrealized
