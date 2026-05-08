"""Execution metrics helpers shared by read/write paths."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.summary import TaskSummary
from apps.trading.utils import AccountCurrency, Instrument


class ExecutionMetricsBuilder:
    """Build aggregate execution metrics from persisted trading activity."""

    def build(
        self,
        *,
        task,
        task_type: str,
        task_id: str,
        execution_id: str,
        summary: TaskSummary,
        fallback_mid_rate: Decimal | None = None,
    ) -> dict[str, Any]:
        """Build aggregate execution metrics from a summary snapshot."""
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
        with_pnl = closed_qs.annotate(pnl_value=pnl_expr)
        wins_losses = with_pnl.aggregate(
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
        winning_trades = int(wins_losses["winning_trades"] or 0)
        losing_trades = int(wins_losses["losing_trades"] or 0)
        total_trades = int(
            Trade.objects.filter(
                task_type=task_type,
                task_id=task_id,
                execution_id=execution_id,
            ).count()
        )
        decisions = winning_trades + losing_trades
        win_rate = (
            (Decimal(winning_trades) / Decimal(decisions) * Decimal("100"))
            if decisions > 0
            else Decimal("0")
        )

        total_pnl = summary.pnl.realized + summary.pnl.unrealized
        mid_rate = summary.tick.mid or fallback_mid_rate

        # Determine quote to account conversion so overview values are
        # denominated consistently with current balance and metrics tab values.
        account_ccy = getattr(task, "account_currency", "USD") or "USD"
        instrument = Instrument(getattr(task, "instrument", "") or "")
        conv = Decimal("1")
        if instrument.name and mid_rate and mid_rate > 0:
            conv = instrument.quote_to_account_rate(mid_rate, AccountCurrency(account_ccy))

        realized_pnl_acct = summary.pnl.realized * conv
        unrealized_pnl_acct = summary.pnl.unrealized * conv
        total_pnl_acct = realized_pnl_acct + unrealized_pnl_acct

        initial_balance = getattr(task, "initial_balance", None)
        total_return: Decimal | None = None
        if task_type == "backtest" and initial_balance:
            try:
                initial = Decimal(str(initial_balance))
                if initial != Decimal("0"):
                    total_return = (total_pnl_acct / initial * Decimal("100")).quantize(
                        Decimal("0.0000000001")
                    )
            except Exception:
                pass  # nosec B110

        metrics: dict[str, Any] = {
            "total_pnl": total_pnl_acct,
            "realized_pnl": realized_pnl_acct,
            "unrealized_pnl": unrealized_pnl_acct,
            "total_pnl_quote": total_pnl,
            "realized_pnl_quote": summary.pnl.realized,
            "unrealized_pnl_quote": summary.pnl.unrealized,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate.quantize(Decimal("0.0001")),
            "current_balance": summary.execution.current_balance,
            "initial_balance": str(getattr(task, "initial_balance", None) or ""),
            "open_positions": summary.counts.open_positions,
            "closed_positions": summary.counts.closed_positions,
            "ticks_processed": summary.execution.ticks_processed,
            "pnl_currency": account_ccy.upper(),
            "quote_currency": instrument.quote_currency,
        }
        if total_return is not None:
            metrics["total_return"] = total_return
        return metrics

    def _abs_units(self):
        return Case(
            When(units__lt=0, then=F("units") * Value(-1)),
            default=F("units"),
            output_field=IntegerField(),
        )


def build_execution_metrics(
    *,
    task,
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
