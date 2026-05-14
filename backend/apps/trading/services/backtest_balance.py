"""Backtest execution balance adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.money import Money
from apps.trading.models import BacktestTask, ExecutionState, TaskLog
from apps.trading.services.display_money import DISPLAY_MONEY
from apps.trading.services.execution_snapshots import sync_execution_snapshot


class BacktestBalanceAdjustmentError(Exception):
    """Public, stable validation failure for backtest balance adjustments."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.public_message = message
        self.code = code


@dataclass(frozen=True)
class BacktestBalanceAdjustmentResult:
    """Result returned after changing a resumable backtest execution balance."""

    task_id: UUID
    execution_id: UUID
    previous_balance: Decimal
    previous_balance_currency: str
    current_balance: Decimal
    current_balance_currency: str
    adjustment: Decimal
    adjustment_currency: str
    state_version: int
    previous_balance_display_money: dict[str, str] | None = None
    current_balance_display_money: dict[str, str] | None = None
    adjustment_display_money: dict[str, str] | None = None
    display_conversion_context: dict[str, object] | None = None

    @property
    def currency(self) -> str:
        """Return the balance currency shared by every amount in this result."""
        return self.current_balance_currency

    @property
    def previous_balance_money(self) -> Money:
        """Return the previous balance as an amount/currency pair."""
        return Money.coerce(self.previous_balance, self.previous_balance_currency)

    @property
    def current_balance_money(self) -> Money:
        """Return the new current balance as an amount/currency pair."""
        return Money.coerce(self.current_balance, self.current_balance_currency)

    @property
    def adjustment_money(self) -> Money:
        """Return the adjustment as an amount/currency pair."""
        return Money.coerce(self.adjustment, self.adjustment_currency)


@dataclass(frozen=True)
class _BacktestBalanceDisplayValues:
    previous: dict[str, str] | None
    current: dict[str, str] | None
    adjustment: dict[str, str] | None
    conversion_context: dict[str, object] | None


def set_backtest_current_balance(
    *,
    task_id: UUID,
    user_id: int,
    current_balance: Decimal,
    reason: str = "",
) -> BacktestBalanceAdjustmentResult:
    """Set the current balance for a paused or stopped backtest execution."""
    if current_balance < 0:
        raise BacktestBalanceAdjustmentError(
            "Current balance must be zero or greater.",
            code="backtest_balance_negative",
        )

    with transaction.atomic():
        try:
            task = BacktestTask.objects.select_for_update().get(
                pk=task_id,
                user_id=user_id,
            )
        except BacktestTask.DoesNotExist as exc:
            raise BacktestBalanceAdjustmentError(
                "Backtest task was not found.",
                code="backtest_balance_task_not_found",
            ) from exc

        if task.status not in {TaskStatus.PAUSED, TaskStatus.STOPPED}:
            raise BacktestBalanceAdjustmentError(
                "Backtest task must be paused or stopped before changing balance.",
                code="backtest_balance_requires_paused_or_stopped",
            )

        if task.execution_id is None:
            raise BacktestBalanceAdjustmentError(
                "Backtest task has no active execution state.",
                code="backtest_balance_missing_execution",
            )

        try:
            state = ExecutionState.objects.select_for_update().get(
                task_type=TaskType.BACKTEST,
                task_id=task.pk,
                execution_id=task.execution_id,
            )
        except ExecutionState.DoesNotExist as exc:
            raise BacktestBalanceAdjustmentError(
                "Backtest execution state was not found.",
                code="backtest_balance_state_not_found",
            ) from exc

        account_currency = str(task.account_currency or "").strip().upper()
        previous_balance_money = Money.coerce(state.current_balance, account_currency)
        current_balance_money = Money.coerce(current_balance, account_currency)
        adjustment_money = current_balance_money.subtract(previous_balance_money)
        previous_balance = previous_balance_money.amount
        adjustment = adjustment_money.amount
        updated_at = timezone.now()
        display_values = _display_balance_values(
            previous_balance_money=previous_balance_money,
            current_balance_money=current_balance_money,
            adjustment_money=adjustment_money,
            task=task,
            as_of=updated_at,
        )
        ExecutionState.objects.filter(pk=state.pk).update(
            current_balance=current_balance_money.amount,
            current_balance_currency=account_currency,
            updated_at=updated_at,
            state_version=F("state_version") + 1,
        )
        task.updated_at = updated_at
        task.save(update_fields=["updated_at"])
        state.refresh_from_db(
            fields=["current_balance", "current_balance_currency", "state_version"]
        )

        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            level=LogLevel.INFO,
            component="backtest.balance_adjustment",
            message="Backtest current balance changed",
            details={
                "event": "backtest_balance_adjusted",
                "previous_balance": str(previous_balance),
                "previous_balance_money": previous_balance_money.as_dict(),
                "current_balance": str(state.current_balance),
                "current_balance_money": Money.coerce(
                    state.current_balance,
                    account_currency,
                ).as_dict(),
                "adjustment": str(adjustment),
                "adjustment_money": adjustment_money.as_dict(),
                "previous_balance_display_money": display_values.previous,
                "current_balance_display_money": display_values.current,
                "adjustment_display_money": display_values.adjustment,
                "display_conversion_context": _json_safe_conversion_context(
                    display_values.conversion_context
                ),
                "currency": account_currency,
                "reason": reason,
            },
        )
        _refresh_balance_dependent_snapshots(task)

        return BacktestBalanceAdjustmentResult(
            task_id=task.pk,
            execution_id=task.execution_id,
            previous_balance=previous_balance,
            previous_balance_currency=account_currency,
            current_balance=Decimal(str(state.current_balance)),
            current_balance_currency=account_currency,
            adjustment=adjustment,
            adjustment_currency=account_currency,
            state_version=state.state_version,
            previous_balance_display_money=display_values.previous,
            current_balance_display_money=display_values.current,
            adjustment_display_money=display_values.adjustment,
            display_conversion_context=display_values.conversion_context,
        )


def _display_balance_values(
    *,
    previous_balance_money: Money,
    current_balance_money: Money,
    adjustment_money: Money,
    task: BacktestTask,
    as_of: datetime,
) -> _BacktestBalanceDisplayValues:
    """Return display-currency balance values and conversion metadata."""
    source_currency = current_balance_money.currency_code
    target_currency = (
        str(
            getattr(task, "effective_display_currency", "")
            or getattr(task, "display_currency", "")
            or source_currency
        )
        .strip()
        .upper()
    )
    converted = DISPLAY_MONEY.convert_many(
        {
            "previous": previous_balance_money,
            "current": current_balance_money,
            "adjustment": adjustment_money,
        },
        target_currency=target_currency,
        instrument=str(getattr(task, "instrument", "") or ""),
        as_of=as_of,
    )
    return _BacktestBalanceDisplayValues(
        previous=converted.values["previous"],
        current=converted.values["current"],
        adjustment=converted.values["adjustment"],
        conversion_context=converted.conversion_context,
    )


def _json_safe_conversion_context(value: dict[str, object] | None) -> dict[str, object] | None:
    """Return conversion metadata with JSONField-safe primitive values."""
    if value is None:
        return None
    result = dict(value)
    if result.get("rate") is not None:
        result["rate"] = str(result["rate"])
    rate_as_of = result.get("rate_as_of")
    if isinstance(rate_as_of, datetime):
        result["rate_as_of"] = rate_as_of.isoformat()
    return result


def _refresh_balance_dependent_snapshots(task: BacktestTask) -> None:
    """Refresh terminal snapshot data that includes execution balance."""
    if task.execution_id is None:
        return

    cache.delete(f"task-summary-snapshot:{TaskType.BACKTEST}:{task.pk}:{task.execution_id}")
    sync_execution_snapshot(task=task, task_type=TaskType.BACKTEST)
