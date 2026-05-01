"""Runtime metric restoration and resume continuity checks."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from logging import Logger
from typing import Any, Protocol

from django.db.models import Case, F, Sum, Value, When

from apps.trading.models import ExecutionMetricAggregate
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.utils import quote_to_account_rate


class MetricResumeExecutor(Protocol):
    task: Any
    task_type: Any
    instrument: str
    logger: Logger
    _runtime_metrics: Any


class RuntimeMetricResumeCoordinator:
    """Restores cumulative runtime metric counters on task resume."""

    def __init__(self, executor: MetricResumeExecutor) -> None:
        self.executor = executor

    def restore_counters(self, *, state: Any) -> None:
        """Restore counters from state metrics, falling back to DB aggregation."""
        persisted_metrics = _persisted_metrics(state)
        if persisted_metrics:
            self._restore_from_persisted_metrics(state=state, metrics=persisted_metrics)
            return
        self._restore_from_database(state=state)

    def validate_continuity(self, *, state: Any) -> None:
        """Warn when resumed state deviates from the latest persisted snapshot."""
        executor = self.executor
        try:
            aggregate = (
                ExecutionMetricAggregate.objects.filter(
                    task_type=executor.task_type.value,
                    task_id=executor.task.pk,
                    execution_id=executor.task.execution_id,
                )
                .only("latest_metrics", "continuity_warnings")
                .first()
            )
        except Exception:  # pragma: no cover - best-effort in non-DB unit tests
            executor.logger.debug(
                "Skipping resume continuity check (aggregate lookup unavailable)",
                exc_info=True,
            )
            return
        if not aggregate or not isinstance(aggregate.latest_metrics, dict):
            return

        state_metrics = _persisted_metrics(state)
        prev_balance = to_decimal_metric(aggregate.latest_metrics.get("current_balance"))
        resumed_balance = to_decimal_metric(state_metrics.get("current_balance"))
        if prev_balance <= 0 or resumed_balance <= 0:
            return

        delta_ratio = abs((resumed_balance - prev_balance) / prev_balance)
        if delta_ratio < Decimal("0.10"):
            return

        warning = {
            "kind": "resume_balance_jump",
            "previous_balance": str(prev_balance),
            "resumed_balance": str(resumed_balance),
            "delta_ratio": str(delta_ratio),
        }
        executor.logger.warning(
            "Resume continuity warning - task_id=%s, execution_id=%s, payload=%s",
            executor.task.pk,
            executor.task.execution_id,
            warning,
        )
        existing = (
            aggregate.continuity_warnings if isinstance(aggregate.continuity_warnings, list) else []
        )
        aggregate.continuity_warnings = [*existing, warning][-20:]
        aggregate.save(update_fields=["continuity_warnings", "updated_at"])

    def _restore_from_persisted_metrics(self, *, state: Any, metrics: dict[str, Any]) -> None:
        realized_pnl = to_decimal_metric(metrics.get("realized_pnl"))
        realized_pnl_quote = to_decimal_metric(metrics.get("realized_pnl_quote"))
        if realized_pnl_quote == Decimal("0") and realized_pnl != Decimal("0"):
            conversion = self._quote_to_account_rate(state)
            if conversion > 0:
                realized_pnl_quote = realized_pnl / conversion

        self.executor._runtime_metrics.restore_counters(
            realized_pnl=realized_pnl,
            realized_pnl_quote=realized_pnl_quote,
            total_trades=to_int_metric(metrics.get("total_trades")),
            closed_positions=to_int_metric(metrics.get("closed_positions")),
            winning_trades=to_int_metric(metrics.get("winning_trades")),
            losing_trades=to_int_metric(metrics.get("losing_trades")),
        )

    def _restore_from_database(self, *, state: Any) -> None:
        executor = self.executor
        base_filter = {
            "task_type": executor.task_type.value,
            "task_id": str(executor.task.pk),
        }
        if executor.task.execution_id:
            base_filter["execution_id"] = executor.task.execution_id

        abs_units = Case(When(units__lt=0, then=-F("units")), default=F("units"))
        closed_qs = Position.objects.filter(**base_filter, is_open=False).exclude(
            exit_price__isnull=True
        )
        agg = closed_qs.aggregate(
            realized_pnl=Sum(
                Case(
                    When(direction="long", then=(F("exit_price") - F("entry_price")) * abs_units),
                    When(direction="short", then=(F("entry_price") - F("exit_price")) * abs_units),
                    default=Value(Decimal("0")),
                )
            ),
            winning=Sum(
                Case(
                    When(
                        direction="long",
                        then=Case(
                            When(exit_price__gt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    When(
                        direction="short",
                        then=Case(
                            When(exit_price__lt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    default=Value(0),
                )
            ),
            losing=Sum(
                Case(
                    When(
                        direction="long",
                        then=Case(
                            When(exit_price__lt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    When(
                        direction="short",
                        then=Case(
                            When(exit_price__gt=F("entry_price"), then=Value(1)),
                            default=Value(0),
                        ),
                    ),
                    default=Value(0),
                )
            ),
        )

        realized_pnl_quote = agg["realized_pnl"] or Decimal("0")
        conversion = self._quote_to_account_rate(state)
        realized_pnl = realized_pnl_quote * conversion if conversion > 0 else realized_pnl_quote
        executor._runtime_metrics.restore_counters(
            realized_pnl=realized_pnl,
            realized_pnl_quote=realized_pnl_quote,
            total_trades=Trade.objects.filter(
                **base_filter, execution_method="open_position"
            ).count(),
            closed_positions=closed_qs.count(),
            winning_trades=agg["winning"] or 0,
            losing_trades=agg["losing"] or 0,
        )

    def _quote_to_account_rate(self, state: Any) -> Decimal:
        executor = self.executor
        account_currency = getattr(executor.task, "account_currency", "") or getattr(
            getattr(executor.task, "oanda_account", None), "currency", ""
        )
        last_mid = to_decimal_metric(state.last_tick_price)
        return quote_to_account_rate(
            executor.instrument,
            last_mid if last_mid > 0 else Decimal("1"),
            str(account_currency or ""),
        )


def to_decimal_metric(value: object) -> Decimal:
    """Parse metric payload values into Decimal safely."""
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def to_int_metric(value: object) -> int:
    """Parse metric payload values into int safely."""
    if isinstance(value, int):
        return value
    if value in (None, ""):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _persisted_metrics(state: Any) -> dict[str, Any]:
    strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
    metrics = strategy_state.get("metrics")
    return metrics if isinstance(metrics, dict) else {}
