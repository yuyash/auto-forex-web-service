"""Execution metrics helpers shared by read/write paths."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.summary import TaskSummary


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
    closed_qs = Position.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        is_open=False,
    ).exclude(exit_price__isnull=True)

    pnl_expr = Case(
        When(
            direction="long",
            then=(F("exit_price") - F("entry_price")) * _abs_units(),
        ),
        When(
            direction="short",
            then=(F("entry_price") - F("exit_price")) * _abs_units(),
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
    total_return = compute_total_return(
        task=task,
        task_type=task_type,
        current_balance=summary.execution.current_balance,
        total_pnl=total_pnl,
        mid_rate=mid_rate,
    )

    metrics: dict[str, Any] = {
        "total_pnl": total_pnl,
        "unrealized_pnl": summary.pnl.unrealized,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate.quantize(Decimal("0.0001")),
    }
    if total_return is not None:
        metrics["total_return"] = total_return
    return metrics


def compute_total_return(
    *,
    task,
    task_type: str,
    current_balance: Decimal | None,
    total_pnl: Decimal,
    mid_rate: Decimal | None,
) -> Decimal | None:
    """Compute total return % from current balance vs initial balance."""
    if task_type != "backtest":
        return None
    initial_balance: Decimal | None = getattr(task, "initial_balance", None)
    if not initial_balance:
        return None
    try:
        initial = Decimal(str(initial_balance))
        if initial == Decimal("0"):
            return None

        if current_balance is not None:
            pnl_delta = Decimal(str(current_balance)) - initial
        else:
            pnl_delta = total_pnl
            account_ccy = getattr(task, "account_currency", "USD").upper()
            instrument = getattr(task, "instrument", "")
            quote_ccy = instrument.split("_")[-1].upper() if "_" in instrument else ""
            if quote_ccy and account_ccy != quote_ccy and mid_rate and mid_rate > 0:
                pnl_delta = pnl_delta / mid_rate

        return (pnl_delta / initial * Decimal("100")).quantize(Decimal("0.0000000001"))
    except Exception:
        return None


def _abs_units():
    return Case(
        When(units__lt=0, then=F("units") * Value(-1)),
        default=F("units"),
        output_field=IntegerField(),
    )
