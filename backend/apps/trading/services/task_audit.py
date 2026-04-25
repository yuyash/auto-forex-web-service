"""Structured audit logs for user-driven task and config edits."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.trading.enums import LogLevel
from apps.trading.models import BacktestTask, TaskLog, TradingTask
from apps.trading.services.execution_snapshots import _make_json_safe


def changed_field_values(
    instance: Any, validated_data: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Return old/new values for fields that changed on an instance."""
    changes: dict[str, dict[str, Any]] = {}
    for field, new_value in validated_data.items():
        old_value = getattr(instance, field, None)
        old_safe = _safe_value(old_value)
        new_safe = _safe_value(new_value)
        if old_safe != new_safe:
            changes[field] = {"previous": old_safe, "current": new_safe}
    return changes


def audit_task_update(*, task: BacktestTask | TradingTask, task_type: str, changes: dict) -> None:
    """Persist a task metadata/settings audit log."""
    if not changes:
        return
    TaskLog.objects.create(
        task_type=task_type,
        task_id=task.pk,
        execution_id=getattr(task, "execution_id", None),
        level=LogLevel.INFO,
        component="task.audit",
        message="Task settings updated",
        details={"changed_fields": sorted(changes), "changes": changes},
    )


def audit_strategy_config_update(*, config: Any, changes: dict) -> None:
    """Persist audit logs on tasks affected by a strategy configuration edit."""
    if not changes:
        return
    if not isinstance(getattr(config, "pk", None), UUID):
        return
    details = {
        "configuration_id": str(config.pk),
        "configuration_name": config.name,
        "changed_fields": sorted(changes),
        "changes": changes,
    }
    logs = []
    for task in BacktestTask.objects.filter(config=config).only("id", "execution_id"):
        logs.append(
            TaskLog(
                task_type="backtest",
                task_id=task.pk,
                execution_id=task.execution_id,
                level=LogLevel.INFO,
                component="config.audit",
                message="Strategy configuration updated",
                details=details,
            )
        )
    for task in TradingTask.objects.filter(config=config).only("id", "execution_id"):
        logs.append(
            TaskLog(
                task_type="trading",
                task_id=task.pk,
                execution_id=task.execution_id,
                level=LogLevel.INFO,
                component="config.audit",
                message="Strategy configuration updated",
                details=details,
            )
        )
    if logs:
        TaskLog.objects.bulk_create(logs)


def _safe_value(value: Any) -> Any:
    if hasattr(value, "pk"):
        return str(value.pk)
    try:
        return _make_json_safe(value)
    except TypeError:
        return str(value)
