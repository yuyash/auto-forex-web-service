"""Central task status and permission policy."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from apps.trading.enums import TaskStatus

WORKER_OWNED_STATUSES = frozenset(
    {
        TaskStatus.STARTING,
        TaskStatus.RUNNING,
        TaskStatus.IDLE,
        TaskStatus.DRAINING,
        TaskStatus.STOPPING,
    }
)
TERMINAL_STATUSES = frozenset(
    {
        TaskStatus.STOPPED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    }
)
METADATA_FIELDS = frozenset({"name", "description"})
EXECUTION_SETTING_FIELDS = frozenset(
    {
        "config",
        "config_id",
        "instrument",
        "pip_size",
        "data_source",
        "start_time",
        "end_time",
        "initial_balance",
        "account_currency",
        "tick_granularity",
        "tick_window_value_mode",
        "hedging_enabled",
        "trading_mode",
        "oanda_account",
        "account_id",
        "live_tick_stale_guard_enabled",
        "live_tick_max_age_seconds",
        "live_tick_status_log_interval_seconds",
        "broker_drift_check_interval_seconds",
    }
)


@dataclass(frozen=True)
class TaskActionPolicy:
    """Frontend-safe task action flags."""

    can_start: bool
    can_stop: bool
    can_pause: bool
    can_resume: bool
    can_restart: bool
    can_delete: bool
    can_edit_metadata: bool
    can_edit_execution_settings: bool
    restart_required_for_execution_edits: bool

    def as_dict(self) -> dict[str, bool]:
        """Return policy as a JSON-serializable dict."""
        return asdict(self)


def is_worker_owned_status(status: str | TaskStatus | None) -> bool:
    """Return whether a task status is actively owned by a worker."""
    return _normalize_status(status) in WORKER_OWNED_STATUSES


def action_policy_for_task(task: Any, *, task_type: str) -> TaskActionPolicy:
    """Compute action permissions for a task object."""
    status = _normalize_status(getattr(task, "status", None))
    is_trading = task_type == "trading"
    can_resume = bool(getattr(task, "can_resume", lambda: False)())

    return TaskActionPolicy(
        can_start=status == TaskStatus.CREATED,
        can_stop=status
        in {
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.IDLE,
            TaskStatus.DRAINING,
            *(() if is_trading else (TaskStatus.PAUSED,)),
        },
        can_pause=(not is_trading and status == TaskStatus.RUNNING),
        can_resume=can_resume,
        can_restart=status in TERMINAL_STATUSES,
        can_delete=status
        in {
            TaskStatus.CREATED,
            TaskStatus.STOPPED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
        },
        can_edit_metadata=not is_worker_owned_status(status),
        can_edit_execution_settings=status
        in {
            TaskStatus.CREATED,
            TaskStatus.STOPPED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            *(() if is_trading else (TaskStatus.PAUSED,)),
        },
        restart_required_for_execution_edits=status in TERMINAL_STATUSES,
    )


def validate_task_update_fields(
    *,
    task: Any,
    changed_fields: set[str],
    task_type: str,
) -> None:
    """Validate whether changed fields may be updated in the task's state."""
    error = task_update_validation_error(
        task=task,
        changed_fields=changed_fields,
        task_type=task_type,
    )
    if error is not None:
        raise ValueError(error)


def task_update_validation_error(
    *,
    task: Any,
    changed_fields: set[str],
    task_type: str,
) -> str | None:
    """Return a public validation error for an invalid task update."""
    policy = action_policy_for_task(task, task_type=task_type)
    status = _normalize_status(getattr(task, "status", None))

    if is_worker_owned_status(status):
        return "Cannot update a task while it is actively running. Stop or pause it first."

    execution_fields = changed_fields & EXECUTION_SETTING_FIELDS
    if execution_fields and not policy.can_edit_execution_settings:
        fields = ", ".join(sorted(execution_fields))
        return (
            f"Cannot update execution settings ({fields}) while task is {status}. "
            "Stop the task or edit only name and description."
        )

    return None


def _normalize_status(status: str | TaskStatus | None) -> TaskStatus | None:
    if isinstance(status, TaskStatus):
        return status
    if status is None:
        return None
    try:
        return TaskStatus(str(status))
    except ValueError:
        return None
