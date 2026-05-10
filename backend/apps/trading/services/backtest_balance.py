"""Backtest execution balance adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.money import Money
from apps.trading.models import BacktestTask, ExecutionState, TaskLog
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
        )


def _refresh_balance_dependent_snapshots(task: BacktestTask) -> None:
    """Refresh terminal snapshot data that includes execution balance."""
    if task.execution_id is None:
        return

    cache.delete(f"task-summary-snapshot:{TaskType.BACKTEST}:{task.pk}:{task.execution_id}")
    sync_execution_snapshot(task=task, task_type=TaskType.BACKTEST)
