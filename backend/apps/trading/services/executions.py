"""Execution history service."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When

from apps.trading.enums import TaskStatus
from apps.trading.models import CeleryTaskStatus
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.summary import compute_task_summary


@dataclass(frozen=True)
class TaskExecutionRow:
    """Execution metadata row for API responses."""

    id: str
    task_type: str
    task_id: str
    execution_number: str
    status: str
    progress: int
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    error_traceback: str | None
    duration: float | None
    created_at: str
    metrics: dict[str, Any] | None = None


def list_task_executions(
    *, task, task_type: str, include_metrics: bool = False
) -> list[dict[str, Any]]:
    """List execution history for a task ordered by newest run first."""
    task_id = str(task.pk)
    task_name = (
        "trading.tasks.run_backtest_task"
        if task_type == "backtest"
        else "trading.tasks.run_trading_task"
    )
    prefix = f"{task_id}:"

    by_run_id: dict[str, dict[str, Any]] = {}

    for row in (
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key__startswith=prefix)
        .order_by("-created_at")
        .values(
            "instance_key",
            "status",
            "status_message",
            "started_at",
            "stopped_at",
            "created_at",
        )
    ):
        run_id = _parse_run_id(task_id=task_id, instance_key=str(row["instance_key"]))
        if run_id is None or run_id in by_run_id:
            continue
        by_run_id[run_id] = {
            "status": _map_celery_status(str(row["status"])),
            "error_message": str(row["status_message"]) if row["status"] == "failed" else None,
            "started_at": row["started_at"],
            "completed_at": row["stopped_at"],
            "created_at": row["created_at"],
            "error_traceback": None,
        }

    current_run_id = str(getattr(task, "execution_id", None) or "")
    if current_run_id:
        current = by_run_id.get(current_run_id, {})
        current.update(
            {
                "status": str(task.status),
                "error_message": task.error_message or current.get("error_message"),
                "error_traceback": task.error_traceback
                if task.status == TaskStatus.FAILED
                else current.get("error_traceback"),
                "started_at": task.started_at or current.get("started_at"),
                "completed_at": task.completed_at or current.get("completed_at"),
                "created_at": current.get("created_at") or task.created_at,
            }
        )
        by_run_id[current_run_id] = current

    rows: list[dict[str, Any]] = []
    # Get the latest mid rate from the task's most recent ExecutionState
    # to use as fallback for past executions that no longer have state.
    from apps.trading.models.state import ExecutionState as _ES

    _latest_state = (
        _ES.objects.filter(task_type=task_type, task_id=task_id)
        .exclude(last_tick_price__isnull=True)
        .order_by("-updated_at")
        .values_list("last_tick_price", flat=True)
        .first()
    )
    for run_id in sorted(by_run_id.keys(), reverse=True):
        meta = by_run_id[run_id]
        started_at = meta.get("started_at")
        completed_at = meta.get("completed_at")
        progress = _compute_progress(
            task=task,
            task_type=task_type,
            run_id=run_id,
            status=str(meta.get("status") or TaskStatus.CREATED),
        )
        row: dict[str, Any] = TaskExecutionRow(
            id=run_id,
            task_type=task_type,
            task_id=task_id,
            execution_number=run_id,
            status=str(meta.get("status") or TaskStatus.CREATED),
            progress=progress,
            started_at=started_at.isoformat() if started_at else None,
            completed_at=completed_at.isoformat() if completed_at else None,
            error_message=meta.get("error_message"),
            error_traceback=meta.get("error_traceback"),
            duration=_compute_duration_seconds(started_at, completed_at),
            created_at=(meta.get("created_at") or task.created_at).isoformat(),
            metrics=None,
        ).__dict__

        if include_metrics:
            row["metrics"] = _compute_execution_metrics(
                task=task,
                task_type=task_type,
                task_id=task_id,
                run_id=run_id,
                fallback_mid_rate=_latest_state,
            )
        rows.append(row)

    return rows


def _compute_execution_metrics(
    *, task, task_type: str, task_id: str, run_id: str, fallback_mid_rate: Decimal | None = None
) -> dict[str, Any]:
    summary = compute_task_summary(
        task_type=task_type,
        task_id=task_id,
        execution_id=run_id,
    )
    closed_qs = Position.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=run_id,
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
        Trade.objects.filter(task_type=task_type, task_id=task_id, execution_id=run_id).count()
    )
    decisions = winning_trades + losing_trades
    win_rate = (
        (Decimal(winning_trades) / Decimal(decisions) * Decimal("100"))
        if decisions > 0
        else Decimal("0")
    )

    total_pnl = summary.pnl.realized + summary.pnl.unrealized
    mid_rate = summary.tick.mid or fallback_mid_rate
    total_return = _compute_total_return(
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


def _compute_total_return(
    *,
    task,
    task_type: str,
    current_balance: Decimal | None,
    total_pnl: Decimal,
    mid_rate: Decimal | None,
) -> Decimal | None:
    """Compute total return % from current balance vs initial balance.

    Primary method: use current_balance from ExecutionState.
    current_balance is kept in account currency (e.g. USD) — the executor
    converts realized PnL to account currency before adding it — so the
    delta (current_balance - initial_balance) is already in account currency
    and needs no conversion.

    Fallback: when current_balance is unavailable (e.g. past executions whose
    ExecutionState has been cleaned up), use total_pnl which is aggregated
    from positions in quote currency, so it must be converted via mid_rate
    when account currency != quote currency.
    """
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
            # current_balance is in account currency — no conversion needed
            pnl_delta = Decimal(str(current_balance)) - initial
        else:
            # Fallback: total_pnl is in quote currency
            pnl_delta = total_pnl
            account_ccy = getattr(task, "account_currency", "USD").upper()
            instrument = getattr(task, "instrument", "")
            quote_ccy = instrument.split("_")[-1].upper() if "_" in instrument else ""
            if quote_ccy and account_ccy != quote_ccy and mid_rate and mid_rate > 0:
                pnl_delta = pnl_delta / mid_rate

        return (pnl_delta / initial * Decimal("100")).quantize(Decimal("0.0000000001"))
    except Exception:
        return None


def _compute_progress(*, task, task_type: str, run_id: str, status: str) -> int:
    current_run_id = str(getattr(task, "execution_id", None) or "")
    if run_id == current_run_id:
        summary = compute_task_summary(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=run_id,
        )
        return int(summary.task.progress)
    if status == TaskStatus.COMPLETED:
        return 100
    return 0


def _compute_duration_seconds(started_at, completed_at) -> float | None:
    if not started_at or not completed_at:
        return None
    return max((completed_at - started_at).total_seconds(), 0.0)


def _parse_run_id(*, task_id: str, instance_key: str) -> str | None:
    """Extract the execution UUID from a CeleryTaskStatus instance_key.

    instance_key format: ``{task_id}:{execution_uuid}``
    Returns ``None`` for legacy integer-based keys so they are silently skipped.
    """
    if not instance_key.startswith(f"{task_id}:"):
        return None
    suffix = instance_key.rsplit(":", 1)[1]
    if not suffix:
        return None
    try:
        UUID(suffix)
    except ValueError:
        return None
    return suffix


def _map_celery_status(status: str) -> str:
    mapping = {
        CeleryTaskStatus.Status.RUNNING: TaskStatus.RUNNING,
        CeleryTaskStatus.Status.STOPPED: TaskStatus.STOPPED,
        CeleryTaskStatus.Status.COMPLETED: TaskStatus.COMPLETED,
        CeleryTaskStatus.Status.FAILED: TaskStatus.FAILED,
    }
    return str(mapping.get(status, TaskStatus.CREATED))


def _abs_units():
    return Case(
        When(units__lt=0, then=-F("units")),
        default=F("units"),
    )
