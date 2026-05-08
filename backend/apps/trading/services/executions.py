"""Execution history service."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, overload
from uuid import UUID

from django.core.cache import cache

from apps.trading.enums import TaskStatus
from apps.trading.models import CeleryTaskStatus
from apps.trading.services.execution_metrics import build_execution_metrics
from apps.trading.services.execution_snapshots import get_metrics_snapshot
from apps.trading.services.summary import TASK_SUMMARY_READ_MODEL


EXECUTION_METRICS_CACHE_TTL_SECONDS = 60 * 60
EXECUTION_METRICS_ACTIVE_CACHE_TTL_SECONDS = 15


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


@overload
def list_task_executions(
    *,
    task,
    task_type: str,
    include_metrics: bool = False,
    page: int,
    page_size: int,
) -> tuple[int, list[dict[str, Any]]]: ...


@overload
def list_task_executions(
    *,
    task,
    task_type: str,
    include_metrics: bool = False,
    page: None = None,
    page_size: None = None,
) -> list[dict[str, Any]]: ...


def list_task_executions(
    *,
    task,
    task_type: str,
    include_metrics: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[dict[str, Any]] | tuple[int, list[dict[str, Any]]]:
    """List execution history for a task ordered by newest run first.

    When ``page`` and ``page_size`` are provided, returns ``(total_count, rows)``
    so callers can paginate before metric aggregation.
    """
    ordered_run_ids, by_run_id, fallback_mid_rate = _load_execution_index(
        task=task,
        task_type=task_type,
    )
    total_count = len(ordered_run_ids)

    if page is not None and page_size is not None:
        start = max(page - 1, 0) * page_size
        end = start + page_size
        ordered_run_ids = ordered_run_ids[start:end]

    rows = [
        _serialize_execution_row(
            task=task,
            task_type=task_type,
            run_id=run_id,
            meta=by_run_id[run_id],
            include_metrics=include_metrics,
            fallback_mid_rate=fallback_mid_rate,
        )
        for run_id in ordered_run_ids
    ]

    if page is not None and page_size is not None:
        return total_count, rows
    return rows


def get_task_execution(
    *,
    task,
    task_type: str,
    execution_id: str,
    include_metrics: bool = False,
) -> dict[str, Any] | None:
    """Return a single execution row when it exists for the task."""
    meta = _load_execution_meta(task=task, task_type=task_type, run_id=execution_id)
    if meta is None:
        return None
    fallback_mid_rate = _load_latest_fallback_mid_rate(task_type=task_type, task_id=str(task.pk))
    return _serialize_execution_row(
        task=task,
        task_type=task_type,
        run_id=execution_id,
        meta=meta,
        include_metrics=include_metrics,
        fallback_mid_rate=fallback_mid_rate,
    )


def _load_execution_index(
    *, task, task_type: str
) -> tuple[list[str], dict[str, dict[str, Any]], Decimal | None]:
    """Build execution metadata keyed by run ID and return sorted run IDs."""
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

    # Get the latest mid rate from the task's most recent ExecutionState
    # to use as fallback for past executions that no longer have state.
    latest_state = _load_latest_fallback_mid_rate(task_type=task_type, task_id=task_id)
    return (
        sorted(
            by_run_id.keys(), key=lambda rid: by_run_id[rid].get("created_at") or "", reverse=True
        ),
        by_run_id,
        latest_state,
    )


def _load_execution_meta(*, task, task_type: str, run_id: str) -> dict[str, Any] | None:
    task_id = str(task.pk)
    current_run_id = str(getattr(task, "execution_id", None) or "")
    current_meta: dict[str, Any] | None = None
    if run_id == current_run_id:
        current_meta = {
            "status": str(task.status),
            "error_message": task.error_message or None,
            "error_traceback": task.error_traceback if task.status == TaskStatus.FAILED else None,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "created_at": task.created_at,
        }

    task_name = (
        "trading.tasks.run_backtest_task"
        if task_type == "backtest"
        else "trading.tasks.run_trading_task"
    )
    row = (
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=f"{task_id}:{run_id}")
        .order_by("-created_at")
        .values(
            "status",
            "status_message",
            "started_at",
            "stopped_at",
            "created_at",
        )
        .first()
    )
    if row is None:
        return current_meta

    meta = {
        "status": _map_celery_status(str(row["status"])),
        "error_message": str(row["status_message"]) if row["status"] == "failed" else None,
        "started_at": row["started_at"],
        "completed_at": row["stopped_at"],
        "created_at": row["created_at"],
        "error_traceback": None,
    }
    if current_meta:
        meta.update(
            {
                "status": current_meta["status"],
                "error_message": current_meta["error_message"] or meta.get("error_message"),
                "error_traceback": current_meta["error_traceback"],
                "started_at": current_meta["started_at"] or meta.get("started_at"),
                "completed_at": current_meta["completed_at"] or meta.get("completed_at"),
                "created_at": meta.get("created_at") or current_meta["created_at"],
            }
        )
    return meta


def _load_latest_fallback_mid_rate(*, task_type: str, task_id: str) -> Decimal | None:
    from apps.trading.models.state import ExecutionState as _ES

    return (
        _ES.objects.filter(task_type=task_type, task_id=task_id)
        .exclude(last_tick_price__isnull=True)
        .order_by("-updated_at")
        .values_list("last_tick_price", flat=True)
        .first()
    )


def _serialize_execution_row(
    *,
    task,
    task_type: str,
    run_id: str,
    meta: dict[str, Any],
    include_metrics: bool,
    fallback_mid_rate: Decimal | None,
) -> dict[str, Any]:
    task_id = str(task.pk)
    started_at = meta.get("started_at")
    completed_at = meta.get("completed_at")
    progress = _compute_progress(
        task=task,
        task_type=task_type,
        run_id=run_id,
        status=str(meta.get("status") or TaskStatus.CREATED),
    )
    row = asdict(
        TaskExecutionRow(
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
        )
    )

    if include_metrics:
        row["metrics"] = _get_cached_execution_metrics(
            task=task,
            task_type=task_type,
            task_id=task_id,
            run_id=run_id,
            meta=meta,
            fallback_mid_rate=fallback_mid_rate,
        )

    # Attach config snapshots and notes when available
    snapshot = _get_config_snapshot(task_type=task_type, task_id=task_id, run_id=run_id)
    if snapshot is not None:
        task_config = snapshot.get("task_config")
        strategy_config = snapshot.get("strategy_config")
        row["task_config"] = task_config
        row["strategy_config"] = strategy_config
        row["segment_index"] = _extract_segment_index(task_config, strategy_config)
        row["config_revision_count"] = _extract_revision_count(task_config, strategy_config)
        row["notes"] = snapshot.get("notes", "")

    return row


def _extract_segment_index(task_config: Any, strategy_config: Any) -> int:
    for config in (strategy_config, task_config):
        if isinstance(config, dict):
            try:
                return int(config.get("segment_index") or 1)
            except (TypeError, ValueError):
                return 1
    return 1


def _extract_revision_count(task_config: Any, strategy_config: Any) -> int:
    return max(_revision_count(task_config), _revision_count(strategy_config))


def _revision_count(config: Any) -> int:
    if not isinstance(config, dict):
        return 0
    revisions = config.get("revisions")
    return len(revisions) if isinstance(revisions, list) else 0


def _get_cached_execution_metrics(
    *,
    task,
    task_type: str,
    task_id: str,
    run_id: str,
    meta: dict[str, Any],
    fallback_mid_rate: Decimal | None = None,
) -> dict[str, Any]:
    persisted_metrics = get_metrics_snapshot(
        task=task,
        task_type=task_type,
        task_id=task_id,
        execution_id=run_id,
    )
    if persisted_metrics is not None:
        return persisted_metrics

    cache_key = _build_execution_metrics_cache_key(
        task=task,
        task_type=task_type,
        task_id=task_id,
        run_id=run_id,
        meta=meta,
    )
    cached_metrics = cache.get(cache_key)
    if isinstance(cached_metrics, dict):
        return cached_metrics

    metrics = _compute_execution_metrics(
        task=task,
        task_type=task_type,
        task_id=task_id,
        run_id=run_id,
        fallback_mid_rate=fallback_mid_rate,
    )
    status = str(meta.get("status") or "")
    is_terminal = status in {TaskStatus.COMPLETED, TaskStatus.STOPPED, TaskStatus.FAILED}
    ttl = (
        EXECUTION_METRICS_CACHE_TTL_SECONDS
        if is_terminal
        else EXECUTION_METRICS_ACTIVE_CACHE_TTL_SECONDS
    )
    cache.set(cache_key, metrics, ttl)
    return metrics


def _build_execution_metrics_cache_key(
    *, task, task_type: str, task_id: str, run_id: str, meta: dict[str, Any]
) -> str:
    status = str(meta.get("status") or "")
    completed_at = meta.get("completed_at")
    if status in {TaskStatus.COMPLETED, TaskStatus.STOPPED, TaskStatus.FAILED} and completed_at:
        return (
            f"task-execution-metrics-snapshot:{task_type}:{task_id}:{run_id}:"
            f"{completed_at.isoformat()}"
        )
    updated_at = getattr(task, "updated_at", None)
    updated_at_key = updated_at.isoformat() if updated_at else "na"
    return f"task-execution-metrics:{task_type}:{task_id}:{run_id}:{updated_at_key}"


def _compute_execution_metrics(
    *, task, task_type: str, task_id: str, run_id: str, fallback_mid_rate: Decimal | None = None
) -> dict[str, Any]:
    summary = TASK_SUMMARY_READ_MODEL.compute_cached(
        task_type=task_type,
        task_id=task_id,
        execution_id=run_id,
    )
    return build_execution_metrics(
        task=task,
        task_type=task_type,
        task_id=task_id,
        execution_id=run_id,
        summary=summary,
        fallback_mid_rate=fallback_mid_rate,
    )


def _compute_progress(*, task, task_type: str, run_id: str, status: str) -> int:
    current_run_id = str(getattr(task, "execution_id", None) or "")
    if run_id == current_run_id:
        summary = TASK_SUMMARY_READ_MODEL.compute_cached(
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


def _get_config_snapshot(*, task_type: str, task_id: str, run_id: str) -> dict[str, Any] | None:
    """Return task_config, strategy_config, and notes from the execution snapshot."""
    from apps.trading.models import TaskExecutionSnapshot

    row = (
        TaskExecutionSnapshot.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=run_id,
        )
        .values("task_config", "strategy_config", "notes")
        .first()
    )
    if row is None:
        return None
    if not row.get("task_config") and not row.get("strategy_config") and not row.get("notes"):
        return None
    return row


def delete_task_execution(
    *,
    task,
    task_type: str,
    execution_id: str,
) -> bool:
    """Delete a single execution and all its associated data.

    Returns True if the execution was found and deleted, False otherwise.
    """
    from apps.trading.models import CeleryTaskStatus, TaskExecutionSnapshot
    from apps.trading.models.metrics import Metrics
    from apps.trading.models.positions import Position
    from apps.trading.models.state import ExecutionState
    from apps.trading.models.trades import Trade
    from apps.trading.models.events import TradingEvent, StrategyEventRecord

    task_id = str(task.pk)
    task_name = (
        "trading.tasks.run_backtest_task"
        if task_type == "backtest"
        else "trading.tasks.run_trading_task"
    )

    # Check if execution exists
    instance_key = f"{task_id}:{execution_id}"
    exists = CeleryTaskStatus.objects.filter(
        task_name=task_name,
        instance_key=instance_key,
    ).exists()

    current_run_id = str(getattr(task, "execution_id", None) or "")
    if not exists and execution_id != current_run_id:
        return False

    # Delete associated data
    TaskExecutionSnapshot.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    Metrics.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    Position.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    Trade.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    TradingEvent.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    StrategyEventRecord.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    ExecutionState.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
    ).delete()

    CeleryTaskStatus.objects.filter(
        task_name=task_name,
        instance_key=instance_key,
    ).delete()

    # Invalidate cache
    cache_prefix = f"task-execution-metrics:{task_type}:{task_id}:{execution_id}"
    cache_prefix_snapshot = f"task-execution-metrics-snapshot:{task_type}:{task_id}:{execution_id}"
    for prefix in (cache_prefix, cache_prefix_snapshot):
        try:
            cache.delete(prefix)
        except Exception:  # nosec B110
            pass

    return True


def update_execution_notes(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    notes: str,
) -> None:
    """Update notes for an execution snapshot, creating the snapshot if needed."""
    from apps.trading.models import TaskExecutionSnapshot

    TaskExecutionSnapshot.objects.update_or_create(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        defaults={"notes": notes},
    )
