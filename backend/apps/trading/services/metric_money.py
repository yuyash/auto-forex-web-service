"""Currency-aware enrichment for strategy metric snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.trading.money import Money
from apps.trading.services.display_money import DISPLAY_MONEY
from apps.trading.services.fx_rates import FX_CONVERSION, FxConversionService
from apps.trading.utils import Instrument

MONEY_METRIC_KEYS = (
    "current_balance",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "realized_pnl_quote",
    "unrealized_pnl_quote",
    "total_pnl_quote",
    "average_win",
    "average_loss",
)

MONEY_COMPANION_KEYS = (
    "account_currency",
    "quote_currency",
    "pnl_currency",
    "display_currency",
    "display_conversion_context",
)


@dataclass(frozen=True, slots=True)
class MetricMoneyContext:
    """Currency context used to enrich persisted metric rows."""

    account_currency: str
    display_currency: str
    quote_currency: str
    instrument: str


class MetricMoneyEnricher:
    """Attach money objects and display-currency values to metric snapshots."""

    def __init__(
        self,
        context: MetricMoneyContext,
        *,
        fx_conversion: FxConversionService | None = None,
    ) -> None:
        """Initialize an enricher with task-level currency context."""
        self.context = context
        self.fx_conversion = fx_conversion or FX_CONVERSION.with_cache()

    @classmethod
    def for_task(cls, *, task: Any, task_type_label: str) -> "MetricMoneyEnricher":
        """Build an enricher for a backtest or trading task."""
        account_currency = _task_account_currency(task, task_type_label)
        display_currency = _task_display_currency(
            task,
            task_type_label,
            account_currency=account_currency,
        )
        instrument = str(getattr(task, "instrument", "") or "").strip()
        quote_currency = Instrument(instrument).quote_currency
        return cls(
            MetricMoneyContext(
                account_currency=account_currency,
                display_currency=display_currency,
                quote_currency=quote_currency,
                instrument=instrument,
            )
        )

    def enrich(
        self,
        metrics: dict[str, Any],
        *,
        timestamp: datetime | None,
        metric_keys: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Return metrics with currency-aware companions added."""
        roots = requested_money_roots(metric_keys) if metric_keys else MONEY_METRIC_KEYS
        if not roots:
            return metrics

        enriched = dict(metrics)
        money_values: dict[str, Money] = {}
        for key in roots:
            money = self._metric_money(enriched, key)
            if money is None:
                continue
            money_values[key] = money
            enriched.setdefault(f"{key}_money", money.as_dict())
            enriched.setdefault(f"{key}_currency", money.currency_code)

        if not money_values:
            return enriched

        enriched.setdefault("account_currency", self.context.account_currency)
        enriched.setdefault("display_currency", self.context.display_currency)
        if self.context.quote_currency:
            enriched.setdefault("quote_currency", self.context.quote_currency)
        if self.context.instrument:
            enriched.setdefault("instrument", self.context.instrument)

        if self.context.display_currency:
            self._attach_display_money(
                enriched,
                money_values=money_values,
                timestamp=timestamp,
            )

        return enriched

    def _metric_money(self, metrics: dict[str, Any], key: str) -> Money | None:
        value = _decimal_metric(metrics, key)
        if value is None:
            return None
        currency = self._metric_currency(metrics, key)
        if not currency:
            return None
        return Money.coerce(value, currency)

    def _metric_currency(self, metrics: dict[str, Any], key: str) -> str:
        explicit = _currency(metrics.get(f"{key}_currency"))
        if explicit:
            return explicit
        if key == "current_balance":
            return (
                _currency(metrics.get("current_balance_currency"))
                or _currency(metrics.get("account_currency"))
                or self.context.account_currency
            )
        if key.endswith("_quote"):
            return _currency(metrics.get("quote_currency")) or self.context.quote_currency
        return (
            _currency(metrics.get("pnl_currency"))
            or _currency(metrics.get("account_currency"))
            or self.context.account_currency
        )

    def _attach_display_money(
        self,
        metrics: dict[str, Any],
        *,
        money_values: dict[str, Money],
        timestamp: datetime | None,
    ) -> None:
        mid_price = _decimal_metric(metrics, "mid_price")
        values_by_currency: dict[str, dict[str, Money]] = {}
        for key, money in money_values.items():
            values_by_currency.setdefault(money.currency_code, {})[key] = money

        global_context_set = False
        for source_currency, values in values_by_currency.items():
            converted = DISPLAY_MONEY.convert_many(
                values,
                target_currency=self.context.display_currency,
                instrument=self.context.instrument,
                mid_price=mid_price,
                as_of=timestamp,
                fx_conversion=self.fx_conversion,
            )
            context = _jsonable_conversion_context(converted.conversion_context)
            for key, value in converted.values.items():
                metrics[f"{key}_display_money"] = value
                if context is not None:
                    metrics[f"{key}_display_conversion_context"] = context
            if context is not None and (
                not global_context_set or source_currency == self.context.account_currency
            ):
                metrics["display_conversion_context"] = context
                global_context_set = True


def requested_money_roots(metric_keys: tuple[str, ...]) -> tuple[str, ...]:
    """Return money metric roots referenced by a metric key filter."""
    if not metric_keys:
        return ()
    roots: list[str] = []
    for requested in metric_keys:
        root = money_root(requested)
        if root and root not in roots:
            roots.append(root)
    return tuple(roots)


def money_root(key: str) -> str | None:
    """Return the money metric root for a scalar or companion key."""
    if key in MONEY_METRIC_KEYS:
        return key
    for suffix in (
        "_display_conversion_context",
        "_display_money",
        "_money",
        "_currency",
    ):
        if key.endswith(suffix):
            root = key[: -len(suffix)]
            if root in MONEY_METRIC_KEYS:
                return root
    return None


def money_related_keys(root: str) -> tuple[str, ...]:
    """Return scalar and companion keys for a money metric root."""
    return (
        root,
        f"{root}_currency",
        f"{root}_money",
        f"{root}_display_money",
        f"{root}_display_conversion_context",
    )


def _task_account_currency(task: Any, task_type_label: str) -> str:
    if str(task_type_label) == "trading":
        account = getattr(task, "oanda_account", None)
        return _currency(getattr(account, "currency", "")) or _currency(
            getattr(task, "account_currency", "")
        )
    return _currency(getattr(task, "account_currency", ""))


def _task_display_currency(
    task: Any,
    task_type_label: str,
    *,
    account_currency: str,
) -> str:
    if str(task_type_label) == "trading":
        return _currency(getattr(task, "display_currency", "")) or account_currency
    return (
        _currency(getattr(task, "effective_display_currency", ""))
        or _currency(getattr(task, "display_currency", ""))
        or account_currency
    )


def _currency(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code if len(code) == 3 and code.isalpha() else ""


def _decimal_metric(metrics: dict[str, Any], key: str) -> Decimal | None:
    raw = metrics.get(key)
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _jsonable_conversion_context(
    context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if context is None:
        return None
    rate = context.get("rate")
    rate_as_of = context.get("rate_as_of")
    return {
        "source_currency": _currency(context.get("source_currency")),
        "target_currency": _currency(context.get("target_currency")),
        "rate": str(rate) if rate not in (None, "") else None,
        "rate_source": str(context.get("rate_source") or ""),
        "rate_as_of": rate_as_of.isoformat() if isinstance(rate_as_of, datetime) else rate_as_of,
        "rate_path": list(context.get("rate_path") or []),
        "conversion_available": bool(context.get("conversion_available")),
        "conversion_policy": str(context.get("conversion_policy") or "unavailable"),
    }
