"""Backtest execution balance adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import BacktestTask, ExecutionState, TaskLog


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
    current_balance: Decimal
    adjustment: Decimal
    state_version: int


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

        previous_balance = Decimal(str(state.current_balance))
        adjustment = current_balance - previous_balance
        updated_at = timezone.now()
        ExecutionState.objects.filter(pk=state.pk).update(
            current_balance=current_balance,
            updated_at=updated_at,
            state_version=F("state_version") + 1,
        )
        state.refresh_from_db(fields=["current_balance", "state_version"])

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
                "current_balance": str(state.current_balance),
                "adjustment": str(adjustment),
                "reason": reason,
            },
        )

        return BacktestBalanceAdjustmentResult(
            task_id=task.pk,
            execution_id=task.execution_id,
            previous_balance=previous_balance,
            current_balance=Decimal(str(state.current_balance)),
            adjustment=adjustment,
            state_version=state.state_version,
        )
