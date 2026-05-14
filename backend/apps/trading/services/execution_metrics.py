"""Execution metrics helpers shared by read/write paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.money import AccountCurrency, Money
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.conversion_context import CurrencyConversionContext
from apps.trading.services.display_money import DISPLAY_MONEY
from apps.trading.services.fx_rates import FX_CONVERSION, FxRate
from apps.trading.services.summary import TaskSummary
from apps.trading.utils import Instrument


@dataclass(frozen=True, slots=True)
class ExecutionTradeCounts:
    """Trade outcome counters for one execution."""

    total_trades: int
    winning_trades: int
    losing_trades: int

    @property
    def decisions(self) -> int:
        """Return the number of closed positions with non-zero outcome."""
        return self.winning_trades + self.losing_trades

    @property
    def win_rate(self) -> Decimal:
        """Return win rate percentage."""
        if self.decisions <= 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(self.decisions) * Decimal("100")


@dataclass(frozen=True, slots=True)
class ExecutionPnlBreakdown:
    """PnL values in quote and account currencies."""

    realized_quote: Money
    unrealized_quote: Money
    total_quote: Money
    realized_account: Money
    unrealized_account: Money
    total_account: Money
    conversion_rate: Decimal
    conversion_rate_source: str
    conversion_rate_as_of: datetime | None
    conversion_rate_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DisplayPnlMoney:
    """Display-currency PnL values and their conversion metadata."""

    total: Money | None
    realized: Money | None
    unrealized: Money | None
    conversion_context: dict[str, object] | None


class ExecutionTradeOutcomeCollector:
    """Collect trade outcome counts from persisted execution rows."""

    def collect(
        self,
        *,
        task_type: str,
        task_id: str,
        execution_id: str,
    ) -> ExecutionTradeCounts:
        """Return aggregate trade counts for an execution."""
        closed_qs = Position.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            is_open=False,
        ).exclude(exit_price__isnull=True)

        pnl_expr = Case(
            When(
                direction="long",
                then=(F("exit_price") - F("entry_price")) * self._abs_units(),
            ),
            When(
                direction="short",
                then=(F("entry_price") - F("exit_price")) * self._abs_units(),
            ),
            default=Value(Decimal("0")),
            output_field=DecimalField(max_digits=24, decimal_places=10),
        )
        wins_losses = closed_qs.annotate(pnl_value=pnl_expr).aggregate(
            winning_trades=Sum(
                Case(
                    When(pnl_value__gt=0, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            losing_trades=Sum(
                Case(
                    When(pnl_value__lt=0, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        )
        total_trades = int(
            Trade.objects.filter(
                task_type=task_type,
                task_id=task_id,
                execution_id=execution_id,
            ).count()
        )
        return ExecutionTradeCounts(
            total_trades=total_trades,
            winning_trades=int(wins_losses["winning_trades"] or 0),
            losing_trades=int(wins_losses["losing_trades"] or 0),
        )

    def _abs_units(self) -> Case:
        return Case(
            When(units__lt=0, then=F("units") * Value(-1)),
            default=F("units"),
            output_field=IntegerField(),
        )


class ExecutionPnlConverter:
    """Convert quote-currency PnL into the execution account currency."""

    def build(
        self,
        *,
        task: Any,
        summary: TaskSummary,
        fallback_mid_rate: Decimal | None = None,
    ) -> ExecutionPnlBreakdown:
        """Return PnL values paired with their currency codes."""
        account_currency = self.account_currency(task)
        instrument = Instrument(getattr(task, "instrument", "") or "")
        quote_currency = summary.pnl.currency or instrument.quote_currency or account_currency
        total_quote_amount = summary.pnl.realized + summary.pnl.unrealized
        realized_quote = Money.coerce(summary.pnl.realized, quote_currency)
        unrealized_quote = Money.coerce(summary.pnl.unrealized, quote_currency)
        total_quote = Money.coerce(total_quote_amount, quote_currency)

        conversion_rate = self.conversion_rate(
            instrument=instrument,
            account_currency=account_currency,
            mid_rate=summary.tick.mid or fallback_mid_rate,
            as_of=_summary_tick_as_of(summary),
        )
        realized_account = realized_quote.convert(
            rate=conversion_rate.rate,
            target_currency=account_currency,
        )
        unrealized_account = unrealized_quote.convert(
            rate=conversion_rate.rate,
            target_currency=account_currency,
        )
        return ExecutionPnlBreakdown(
            realized_quote=realized_quote,
            unrealized_quote=unrealized_quote,
            total_quote=total_quote,
            realized_account=realized_account,
            unrealized_account=unrealized_account,
            total_account=realized_account.add(unrealized_account),
            conversion_rate=conversion_rate.rate,
            conversion_rate_source=conversion_rate.source,
            conversion_rate_as_of=conversion_rate.as_of,
            conversion_rate_path=conversion_rate.path,
        )

    def account_currency(self, task: Any) -> str:
        """Return the execution account currency, falling back to USD for legacy rows."""
        account_currency = getattr(task, "account_currency", None)
        if not account_currency:
            account = getattr(task, "oanda_account", None)
            account_currency = getattr(account, "currency", None)
        return str(account_currency or "USD").strip().upper()

    def conversion_rate(
        self,
        *,
        instrument: Instrument,
        account_currency: str,
        mid_rate: Decimal | None,
        as_of: datetime | None = None,
    ) -> FxRate:
        """Return quote-to-account conversion for the available market rate."""
        if instrument.name and mid_rate and mid_rate > 0:
            rate = FX_CONVERSION.rate(
                source_currency=instrument.quote_currency,
                target_currency=account_currency,
                instrument=instrument.name,
                mid_price=mid_rate,
                as_of=as_of,
            )
            if rate is not None:
                return rate
            return FxRate(
                instrument.quote_currency,
                AccountCurrency(account_currency).code,
                instrument.quote_to_account_rate(mid_rate, AccountCurrency(account_currency)),
                source="instrument_heuristic",
                path=(instrument.name, "heuristic"),
            )
        return FxRate(
            account_currency,
            account_currency,
            Decimal("1"),
            source="identity",
            path=(account_currency, account_currency),
        )


class ExecutionReturnCalculator:
    """Calculate return percentages from currency-aware balances."""

    def calculate(
        self,
        *,
        task_type: str,
        total_pnl: Money,
        initial_balance: Money | None,
    ) -> Decimal | None:
        """Return total return percentage when an initial account balance exists."""
        if task_type != "backtest" or initial_balance is None:
            return None
        if not initial_balance.currency.matches(total_pnl.currency):
            return None
        if initial_balance.amount == Decimal("0"):
            return None
        return (total_pnl.amount / initial_balance.amount * Decimal("100")).quantize(
            Decimal("0.0000000001")
        )


class ExecutionMetricsSerializer:
    """Serialize metric value objects into the public metrics payload."""

    def serialize(
        self,
        *,
        task: Any,
        task_type: str,
        summary: TaskSummary,
        counts: ExecutionTradeCounts,
        pnl: ExecutionPnlBreakdown,
        total_return: Decimal | None,
    ) -> dict[str, Any]:
        """Build the API-facing metrics dict while preserving legacy keys."""
        account_currency = pnl.total_account.currency_code
        display_currency = (
            str(getattr(task, "display_currency", "") or "").strip().upper()
            or summary.execution.display_currency
            or account_currency
        )
        initial_balance = self.initial_balance_money(task, account_currency=account_currency)
        current_balance_amount = summary.execution.current_balance
        current_balance = Money.coerce(
            current_balance_amount if current_balance_amount is not None else Decimal("0"),
            summary.execution.current_balance_currency or account_currency,
        )
        display_pnl = self._display_pnl_money(
            pnl,
            display_currency,
            task,
            summary,
        )
        metrics: dict[str, Any] = {
            "total_pnl": pnl.total_account.amount,
            "realized_pnl": pnl.realized_account.amount,
            "unrealized_pnl": pnl.unrealized_account.amount,
            "total_pnl_quote": pnl.total_quote.amount,
            "realized_pnl_quote": pnl.realized_quote.amount,
            "unrealized_pnl_quote": pnl.unrealized_quote.amount,
            "total_trades": counts.total_trades,
            "winning_trades": counts.winning_trades,
            "losing_trades": counts.losing_trades,
            "win_rate": counts.win_rate.quantize(Decimal("0.0001")),
            "current_balance": current_balance.amount,
            "initial_balance": str(initial_balance.amount) if initial_balance is not None else "",
            "open_positions": summary.counts.open_positions,
            "closed_positions": summary.counts.closed_positions,
            "ticks_processed": summary.execution.ticks_processed,
            "pnl_currency": account_currency,
            "account_currency": account_currency,
            "quote_currency": pnl.total_quote.currency_code,
            "display_currency": display_currency,
            "current_balance_currency": current_balance.currency_code,
            "initial_balance_currency": (
                initial_balance.currency_code if initial_balance is not None else account_currency
            ),
            "total_pnl_money": pnl.total_account.as_dict(),
            "realized_pnl_money": pnl.realized_account.as_dict(),
            "unrealized_pnl_money": pnl.unrealized_account.as_dict(),
            "total_pnl_quote_money": pnl.total_quote.as_dict(),
            "realized_pnl_quote_money": pnl.realized_quote.as_dict(),
            "unrealized_pnl_quote_money": pnl.unrealized_quote.as_dict(),
            "current_balance_money": current_balance.as_dict(),
            "quote_to_account_rate": pnl.conversion_rate,
            "quote_to_account_rate_source": pnl.conversion_rate_source,
            "quote_to_account_rate_as_of": pnl.conversion_rate_as_of,
            "quote_to_account_rate_path": list(pnl.conversion_rate_path),
        }
        if summary.execution.current_balance_display_money is not None:
            metrics["current_balance_display_money"] = (
                summary.execution.current_balance_display_money
            )
        if display_pnl.conversion_context is not None:
            metrics["display_conversion_context"] = display_pnl.conversion_context
        elif summary.execution.current_balance_display_conversion_context is not None:
            metrics["display_conversion_context"] = (
                summary.execution.current_balance_display_conversion_context
            )
        if total_return is not None:
            metrics["total_return"] = total_return
        if display_pnl.total is not None:
            metrics["total_pnl_display_money"] = display_pnl.total.as_dict()
        if display_pnl.realized is not None:
            metrics["realized_pnl_display_money"] = display_pnl.realized.as_dict()
        if display_pnl.unrealized is not None:
            metrics["unrealized_pnl_display_money"] = display_pnl.unrealized.as_dict()
        if initial_balance is not None:
            metrics["initial_balance_money"] = initial_balance.as_dict()
        return metrics

    def initial_balance_money(self, task: Any, *, account_currency: str) -> Money | None:
        """Return task.initial_balance paired with the account currency."""
        initial_balance = getattr(task, "initial_balance", None)
        if initial_balance is None or initial_balance == "":
            return None
        try:
            return Money.coerce(initial_balance, account_currency)
        except Exception:
            return None

    def _display_pnl_money(
        self,
        pnl: ExecutionPnlBreakdown,
        display_currency: str,
        task: Any,
        summary: TaskSummary,
    ) -> DisplayPnlMoney:
        """Return total/realized/unrealized PnL converted to display currency."""
        target = str(display_currency or "").strip().upper()
        if not target:
            return DisplayPnlMoney(
                total=None,
                realized=None,
                unrealized=None,
                conversion_context=CurrencyConversionContext.unavailable(
                    source_currency=pnl.total_account.currency_code,
                    target_currency=target,
                ).as_dict(),
            )
        money_values = (pnl.total_account, pnl.realized_account, pnl.unrealized_account)
        if pnl.total_account.currency.matches(target):
            return DisplayPnlMoney(
                total=money_values[0],
                realized=money_values[1],
                unrealized=money_values[2],
                conversion_context=CurrencyConversionContext.from_rate(
                    FxRate(
                        pnl.total_account.currency_code,
                        target,
                        Decimal("1"),
                        as_of=_summary_tick_as_of(summary),
                        source="identity",
                        path=(pnl.total_account.currency_code, target),
                    )
                ).as_dict(),
            )
        instrument = getattr(task, "instrument", "") or ""
        converted = DISPLAY_MONEY.convert_many(
            {
                "total": pnl.total_account,
                "realized": pnl.realized_account,
                "unrealized": pnl.unrealized_account,
            },
            target_currency=target,
            instrument=instrument,
            mid_price=summary.tick.mid,
            as_of=_summary_tick_as_of(summary),
        )
        total_money = converted.values["total"]
        realized_money = converted.values["realized"]
        unrealized_money = converted.values["unrealized"]
        if total_money is None or realized_money is None or unrealized_money is None:
            return DisplayPnlMoney(
                total=None,
                realized=None,
                unrealized=None,
                conversion_context=converted.conversion_context,
            )
        return DisplayPnlMoney(
            total=Money.coerce(total_money["amount"], total_money["currency"]),
            realized=Money.coerce(realized_money["amount"], realized_money["currency"]),
            unrealized=Money.coerce(unrealized_money["amount"], unrealized_money["currency"]),
            conversion_context=converted.conversion_context,
        )


def _summary_tick_as_of(summary: TaskSummary) -> datetime | None:
    """Return the summary tick timestamp as a datetime for historical FX lookup."""
    timestamp = summary.tick.timestamp
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(str(timestamp))
    except ValueError:
        return None


class ExecutionMetricsBuilder:
    """Build aggregate execution metrics from persisted trading activity."""

    def __init__(
        self,
        *,
        trade_counts: ExecutionTradeOutcomeCollector | None = None,
        pnl_converter: ExecutionPnlConverter | None = None,
        return_calculator: ExecutionReturnCalculator | None = None,
        serializer: ExecutionMetricsSerializer | None = None,
    ) -> None:
        self.trade_counts = trade_counts or ExecutionTradeOutcomeCollector()
        self.pnl_converter = pnl_converter or ExecutionPnlConverter()
        self.return_calculator = return_calculator or ExecutionReturnCalculator()
        self.serializer = serializer or ExecutionMetricsSerializer()

    def build(
        self,
        *,
        task: Any,
        task_type: str,
        task_id: str,
        execution_id: str,
        summary: TaskSummary,
        fallback_mid_rate: Decimal | None = None,
    ) -> dict[str, Any]:
        """Build aggregate execution metrics from a summary snapshot."""
        counts = self.trade_counts.collect(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
        )
        pnl = self.pnl_converter.build(
            task=task,
            summary=summary,
            fallback_mid_rate=fallback_mid_rate,
        )
        initial_balance = self.serializer.initial_balance_money(
            task,
            account_currency=pnl.total_account.currency_code,
        )
        total_return = self.return_calculator.calculate(
            task_type=task_type,
            total_pnl=pnl.total_account,
            initial_balance=initial_balance,
        )
        return self.serializer.serialize(
            task=task,
            task_type=task_type,
            summary=summary,
            counts=counts,
            pnl=pnl,
            total_return=total_return,
        )


def build_execution_metrics(
    *,
    task: Any,
    task_type: str,
    task_id: str,
    execution_id: str,
    summary: TaskSummary,
    fallback_mid_rate: Decimal | None = None,
) -> dict[str, Any]:
    """Build aggregate execution metrics from a summary snapshot."""
    return ExecutionMetricsBuilder().build(
        task=task,
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        summary=summary,
        fallback_mid_rate=fallback_mid_rate,
    )
