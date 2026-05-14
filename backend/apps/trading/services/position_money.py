"""Currency-aware enrichment for task position rows."""

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
class PositionMoneyContext:
    """Task-level currency context for position money values."""

    display_currency: str
    instrument: str


class PositionMoneyEnricher:
    """Attach source and display-currency money payloads to positions."""

    def __init__(
        self,
        context: PositionMoneyContext,
        *,
        fx_conversion: FxConversionService | None = None,
    ) -> None:
        """Initialize the enricher with task-level currency context."""
        self.context = context
        self.fx_conversion = fx_conversion or FX_CONVERSION.with_cache()

    @classmethod
    def for_task(cls, *, task: Any, task_type_label: str) -> "PositionMoneyEnricher":
        """Build a position money enricher for a backtest or trading task."""
        money_context = TASK_MONEY_CONTEXT.build(
            task,
            task_type=_task_type(task_type_label),
        )
        return cls(
            PositionMoneyContext(
                display_currency=money_context.display_currency,
                instrument=str(getattr(task, "instrument", "") or "").strip(),
            )
        )

    def enrich_positions(self, positions: list[Any]) -> list[Any]:
        """Return positions with PnL money and display-money companions."""
        for position in positions:
            self.enrich_position(position)
        return positions

    def enrich_position(self, position: Any) -> Any:
        """Attach money payloads to a position object or dict in place."""
        self._attach_money(
            position,
            key="realized_pnl",
            value=self._realized_pnl(position),
            mid_price=_decimal_or_none(_get(position, "exit_price")),
            as_of=_datetime_or_none(_get(position, "exit_time")),
        )
        if bool(_get(position, "is_open")):
            self._attach_money(
                position,
                key="unrealized_pnl",
                value=_decimal_or_none(_get(position, "unrealized_pnl")),
                mid_price=None,
                as_of=None,
            )
        return position

    def _attach_money(
        self,
        position: Any,
        *,
        key: str,
        value: Decimal | None,
        mid_price: Decimal | None,
        as_of: datetime | None,
    ) -> None:
        currency = self._position_quote_currency(position)
        if currency:
            _set(position, f"{key}_currency", currency)
        if value is None or not currency:
            return

        source_money = Money.coerce(_money_decimal(value), currency)
        _set(position, f"{key}_money", source_money.as_dict())

        display_currency = self.context.display_currency
        if not display_currency:
            _set(position, f"{key}_display_money", None)
            return

        converted = DISPLAY_MONEY.convert_many(
            {key: source_money},
            target_currency=display_currency,
            instrument=self._position_instrument(position),
            mid_price=mid_price,
            as_of=as_of,
            fx_conversion=self.fx_conversion,
        )
        _set(position, f"{key}_display_money", converted.values.get(key))
        if converted.conversion_context is not None:
            _set(
                position,
                f"{key}_display_conversion_context",
                converted.conversion_context,
            )

    def _realized_pnl(self, position: Any) -> Decimal | None:
        value = _get(position, "realized_pnl")
        if value is None:
            value = _get(position, "_realized_pnl")
        return _decimal_or_none(value)

    def _position_quote_currency(self, position: Any) -> str:
        explicit = _currency(_get(position, "unrealized_pnl_currency"))
        if explicit:
            return explicit
        return _currency(Instrument(self._position_instrument(position)).quote_currency)

    def _position_instrument(self, position: Any) -> str:
        return str(_get(position, "instrument") or self.context.instrument or "").strip()


def _task_type(task_type_label: str) -> TaskTypeLabel:
    return "trading" if str(task_type_label) == "trading" else "backtest"


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _set(obj: Any, name: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[name] = value
    else:
        setattr(obj, name, value)


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


def _money_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0000000001"))
