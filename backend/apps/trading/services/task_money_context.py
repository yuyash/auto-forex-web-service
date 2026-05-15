"""Task-level currency and money context for API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from apps.trading.money import AccountCurrency, Money
from apps.trading.services.task_currencies import instrument_currency_options

TaskType = Literal["backtest", "trading"]
CurrencySource = Literal[
    "backtest_task",
    "task_display_currency",
    "account_currency",
    "oanda_account",
    "unknown",
]
ConversionPolicy = Literal["identity", "runtime_fx_rate", "unavailable"]


@dataclass(frozen=True, slots=True)
class TaskMoneyContext:
    """Task currency choices and money DTOs for task APIs."""

    task_type: TaskType
    account_currency: str
    account_currency_source: CurrencySource
    display_currency: str
    display_currency_source: CurrencySource
    currency_options: tuple[str, ...]
    initial_balance_money: dict[str, str] | None
    commission_per_trade_money: dict[str, str] | None
    display_uses_account_currency: bool
    display_requires_conversion: bool
    conversion_policy: ConversionPolicy

    def as_dict(self) -> dict[str, Any]:
        """Serialize context as JSON-friendly primitives."""
        return {
            "task_type": self.task_type,
            "account_currency": self.account_currency,
            "account_currency_source": self.account_currency_source,
            "display_currency": self.display_currency,
            "display_currency_source": self.display_currency_source,
            "currency_options": list(self.currency_options),
            "initial_balance_money": self.initial_balance_money,
            "commission_per_trade_money": self.commission_per_trade_money,
            "display_uses_account_currency": self.display_uses_account_currency,
            "display_requires_conversion": self.display_requires_conversion,
            "conversion_policy": self.conversion_policy,
        }


class TaskMoneyContextBuilder:
    """Build task-level money context without broker or market-data calls."""

    def build(self, task: Any, *, task_type: TaskType) -> TaskMoneyContext:
        """Return currency choices and money DTOs for a task."""
        account_currency, account_source = self._account_currency(task, task_type=task_type)
        display_currency, display_source = self._display_currency(
            task,
            task_type=task_type,
            account_currency=account_currency,
        )
        currency_options = instrument_currency_options(getattr(task, "instrument", ""))
        display_uses_account_currency = bool(
            account_currency
            and display_currency
            and AccountCurrency(account_currency).matches(display_currency)
        )
        display_requires_conversion = bool(
            account_currency and display_currency and not display_uses_account_currency
        )
        return TaskMoneyContext(
            task_type=task_type,
            account_currency=account_currency,
            account_currency_source=account_source,
            display_currency=display_currency,
            display_currency_source=display_source,
            currency_options=currency_options,
            initial_balance_money=self._money_dict(
                getattr(task, "initial_balance", None),
                account_currency,
            ),
            commission_per_trade_money=self._money_dict(
                getattr(task, "commission_per_trade", None),
                account_currency,
            ),
            display_uses_account_currency=display_uses_account_currency,
            display_requires_conversion=display_requires_conversion,
            conversion_policy=self._conversion_policy(
                display_uses_account_currency=display_uses_account_currency,
                display_requires_conversion=display_requires_conversion,
            ),
        )

    def _account_currency(
        self,
        task: Any,
        *,
        task_type: TaskType,
    ) -> tuple[str, CurrencySource]:
        if task_type == "trading":
            account = getattr(task, "oanda_account", None)
            account_currency = _currency(getattr(account, "currency", ""))
            if not account_currency:
                account_currency = _currency(getattr(task, "account_currency", ""))
            return account_currency, "oanda_account" if account_currency else "unknown"
        account_currency = _currency(getattr(task, "account_currency", ""))
        return account_currency, "backtest_task" if account_currency else "unknown"

    def _display_currency(
        self,
        task: Any,
        *,
        task_type: TaskType,
        account_currency: str,
    ) -> tuple[str, CurrencySource]:
        if task_type == "trading":
            raw_display_currency = _currency(getattr(task, "display_currency", ""))
            if raw_display_currency:
                return raw_display_currency, "task_display_currency"
            return account_currency, "account_currency" if account_currency else "unknown"

        raw_display_currency = _currency(getattr(task, "display_currency", ""))
        if raw_display_currency:
            return raw_display_currency, "task_display_currency"
        return account_currency, "account_currency" if account_currency else "unknown"

    def _money_dict(self, amount: Any, currency: str) -> dict[str, str] | None:
        if amount in (None, "") or not currency:
            return None
        try:
            return Money.coerce(Decimal(str(amount)), currency).as_dict()
        except Exception:
            return None

    def _conversion_policy(
        self,
        *,
        display_uses_account_currency: bool,
        display_requires_conversion: bool,
    ) -> ConversionPolicy:
        if display_uses_account_currency:
            return "identity"
        if display_requires_conversion:
            return "runtime_fx_rate"
        return "unavailable"


def _currency(value: Any) -> str:
    code = str(value or "").strip().upper()
    if len(code) == 3 and code.isalpha():
        return code
    return ""


TASK_MONEY_CONTEXT = TaskMoneyContextBuilder()
