"""Currency-aware enrichment for task trade rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from apps.trading.money import Money
from apps.trading.services.display_money import DISPLAY_MONEY
from apps.trading.services.fx_rates import FX_CONVERSION, FxConversionService
from apps.trading.services.task_money_context import TASK_MONEY_CONTEXT
from apps.trading.utils import Instrument

TaskTypeLabel = Literal["backtest", "trading"]


@dataclass(frozen=True, slots=True)
class TradeMoneyContext:
    """Task-level currency context for trade-row money values."""

    account_currency: str
    display_currency: str
    instrument: str


class TradeMoneyEnricher:
    """Attach source and display-currency money payloads to trade rows."""

    def __init__(
        self,
        context: TradeMoneyContext,
        *,
        fx_conversion: FxConversionService | None = None,
    ) -> None:
        """Initialize the enricher with task-level currency context."""
        self.context = context
        self.fx_conversion = fx_conversion or FX_CONVERSION.with_cache()

    @classmethod
    def for_task(cls, *, task: Any, task_type_label: str) -> "TradeMoneyEnricher":
        """Build a trade money enricher for a backtest or trading task."""
        task_type = _task_type(task_type_label)
        money_context = TASK_MONEY_CONTEXT.build(task, task_type=task_type)
        return cls(
            TradeMoneyContext(
                account_currency=money_context.account_currency,
                display_currency=money_context.display_currency,
                instrument=str(getattr(task, "instrument", "") or "").strip(),
            )
        )

    def enrich_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return rows with PnL money and display-money companions."""
        for row in rows:
            self.enrich_row(row)
        return rows

    def enrich_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Attach money payloads to a single trade row in place."""
        pnl = _decimal_or_none(row.get("pnl"))
        pnl_currency = self._row_quote_currency(row)
        if pnl_currency:
            row.setdefault("pnl_currency", pnl_currency)
        if pnl is None or not pnl_currency:
            return row

        pnl_money = Money.coerce(pnl, pnl_currency)
        row["pnl_money"] = pnl_money.as_dict()

        display_currency = self.context.display_currency
        if not display_currency:
            row["pnl_display_money"] = None
            return row

        display_money = DISPLAY_MONEY.convert_many(
            {"pnl": pnl_money},
            target_currency=display_currency,
            instrument=self._row_instrument(row),
            mid_price=_decimal_or_none(row.get("price")),
            as_of=_datetime_or_none(row.get("timestamp")),
            fx_conversion=self.fx_conversion,
        )
        row["pnl_display_money"] = display_money.values.get("pnl")
        if display_money.conversion_context is not None:
            row["display_conversion_context"] = display_money.conversion_context
        return row

    def _row_quote_currency(self, row: dict[str, Any]) -> str:
        explicit = _currency(row.get("price_currency"))
        if explicit:
            return explicit
        return _currency(Instrument(self._row_instrument(row)).quote_currency)

    def _row_instrument(self, row: dict[str, Any]) -> str:
        return str(row.get("instrument") or self.context.instrument or "").strip()


def _task_type(task_type_label: str) -> TaskTypeLabel:
    return "trading" if str(task_type_label) == "trading" else "backtest"


def _currency(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code if len(code) == 3 and code.isalpha() else ""


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _datetime_or_none(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None
