"""Execution metrics helpers shared by read/write paths."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.summary import TaskSummary
from apps.trading.utils import AccountCurrency, Instrument, Money


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
        quote_currency = instrument.quote_currency or account_currency
        total_quote_amount = summary.pnl.realized + summary.pnl.unrealized
        realized_quote = Money.coerce(summary.pnl.realized, quote_currency)
        unrealized_quote = Money.coerce(summary.pnl.unrealized, quote_currency)
        total_quote = Money.coerce(total_quote_amount, quote_currency)

        conversion_rate = self.conversion_rate(
            instrument=instrument,
            account_currency=account_currency,
            mid_rate=summary.tick.mid or fallback_mid_rate,
        )
        realized_account = realized_quote.convert(
            rate=conversion_rate,
            target_currency=account_currency,
        )
        unrealized_account = unrealized_quote.convert(
            rate=conversion_rate,
            target_currency=account_currency,
        )
        return ExecutionPnlBreakdown(
            realized_quote=realized_quote,
            unrealized_quote=unrealized_quote,
            total_quote=total_quote,
            realized_account=realized_account,
            unrealized_account=unrealized_account,
            total_account=realized_account.add(unrealized_account),
            conversion_rate=conversion_rate,
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
    ) -> Decimal:
        """Return quote-to-account conversion for the available market rate."""
        if instrument.name and mid_rate and mid_rate > 0:
            return instrument.quote_to_account_rate(mid_rate, AccountCurrency(account_currency))
        return Decimal("1")


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
        initial_balance = self.initial_balance_money(task, account_currency=account_currency)
        current_balance_amount = summary.execution.current_balance
        current_balance = Money.coerce(
            current_balance_amount if current_balance_amount is not None else Decimal("0"),
            account_currency,
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
        }
        if initial_balance is not None:
            metrics["initial_balance_money"] = initial_balance.as_dict()
        if total_return is not None:
            metrics["total_return"] = total_return
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
