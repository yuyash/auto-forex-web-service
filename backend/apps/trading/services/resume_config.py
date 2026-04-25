"""Validation and audit helpers for resuming tasks with edited configuration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from apps.trading.models import TaskExecutionSnapshot
from apps.trading.services.execution_snapshots import (
    _make_json_safe,
    _snapshot_strategy_config,
    _snapshot_task_config,
)

RESUME_SAFE_TASK_FIELDS = frozenset(
    {
        "commission_per_trade",
        "sell_on_stop",
        "dry_run",
    }
)
RESUME_MONITORED_PARAMETER_KEYS = (
    "base_units",
    "trend_lot_size",
    "r_max",
    "n_pips_head",
    "n_pips_tail",
    "n_pips_flat_steps",
    "n_pips_gamma",
    "counter_tp_pips",
    "stop_loss_pips_head",
    "stop_loss_pips_tail",
    "margin_cutoff_ratio",
    "loss_cutoff_ratio",
)


@dataclass(frozen=True)
class ResumeConfigAudit:
    """Resume config comparison result."""

    task_changes: dict[str, dict[str, Any]]
    parameter_changes: dict[str, dict[str, Any]]
    effective_parameters: dict[str, Any]
    strategy_type: str | None
    config_name: str | None
    config_hash: str

    @property
    def has_changes(self) -> bool:
        """Return whether the task or strategy parameters changed."""
        return bool(self.task_changes or self.parameter_changes)


def validate_resume_configuration(*, task: Any, task_type: str) -> ResumeConfigAudit:
    """Validate current task/config against the persisted execution snapshot.

    Resuming intentionally keeps the same execution_id and state. That makes
    some edits safe for the next worker invocation, but not all of them. This
    guard blocks known incompatible changes before the task leaves its terminal
    or paused state.
    """
    snapshot = _get_snapshot(task=task, task_type=task_type)
    current_task_config = _safe_task_snapshot(task)
    current_strategy_config = _safe_strategy_snapshot(task)
    current_params = dict(current_strategy_config.get("parameters") or {})

    if snapshot is None:
        return _audit(
            task_changes={},
            parameter_changes={},
            current_strategy_config=current_strategy_config,
        )

    previous_task_config = _current_config(snapshot.task_config)
    previous_strategy_config = _current_config(snapshot.strategy_config)
    previous_params = dict(previous_strategy_config.get("parameters") or {})

    previous_strategy_type = previous_strategy_config.get("strategy_type")
    current_strategy_type = current_strategy_config.get("strategy_type")
    if previous_strategy_type and previous_strategy_type != current_strategy_type:
        raise ValueError(
            "Cannot resume with a different strategy type. Create a new task execution instead."
        )

    task_changes = _diff_dict(previous_task_config, current_task_config)
    blocked_task_fields = sorted(set(task_changes) - RESUME_SAFE_TASK_FIELDS)
    if blocked_task_fields:
        fields = ", ".join(blocked_task_fields)
        raise ValueError(
            f"Cannot resume after changing task execution fields ({fields}). "
            "Restart the task to apply those changes."
        )

    parameter_changes = _diff_dict(previous_params, current_params)
    _validate_strategy_resume_parameter_compatibility(
        strategy_type=current_strategy_type,
        previous_params=previous_params,
        current_params=current_params,
    )

    return _audit(
        task_changes=task_changes,
        parameter_changes=parameter_changes,
        current_strategy_config=current_strategy_config,
    )


def build_config_snapshot_defaults(
    *,
    snapshot: TaskExecutionSnapshot | None,
    task: Any,
) -> dict[str, Any]:
    """Build task/strategy config JSON while preserving resume revision history."""
    current_task_config = _snapshot_task_config(task)
    current_strategy_config = _snapshot_strategy_config(task)
    if snapshot is None:
        return {
            "task_config": _with_config_metadata(current_task_config),
            "strategy_config": _with_config_metadata(current_strategy_config),
        }

    task_config = _merge_config_revision(snapshot.task_config, current_task_config)
    strategy_config = _merge_config_revision(snapshot.strategy_config, current_strategy_config)
    return {
        "task_config": task_config,
        "strategy_config": strategy_config,
    }


def log_effective_resume_configuration(*, logger: Any, audit: ResumeConfigAudit, task: Any) -> None:
    """Log the effective configuration that the next execution will use."""
    monitored = {
        key: audit.effective_parameters.get(key)
        for key in RESUME_MONITORED_PARAMETER_KEYS
        if key in audit.effective_parameters
    }
    logger.info(
        "[CONFIG:RESUME] Effective strategy configuration - task_id=%s, execution_id=%s, "
        "strategy_type=%s, config_name=%s, config_hash=%s, changed=%s, task_changes=%s, "
        "parameter_changes=%s, monitored_parameters=%s",
        task.pk,
        getattr(task, "execution_id", None),
        audit.strategy_type,
        audit.config_name,
        audit.config_hash,
        audit.has_changes,
        sorted(audit.task_changes),
        sorted(audit.parameter_changes),
        monitored,
    )


def log_effective_start_configuration(*, logger: Any, task: Any) -> None:
    """Log the current task/config used by a new worker invocation."""
    strategy_config = _safe_strategy_snapshot(task)
    parameters = dict(strategy_config.get("parameters") or {})
    monitored = {
        key: parameters.get(key) for key in RESUME_MONITORED_PARAMETER_KEYS if key in parameters
    }
    logger.info(
        "[CONFIG:START] Effective strategy configuration - task_id=%s, execution_id=%s, "
        "strategy_type=%s, config_name=%s, config_hash=%s, monitored_parameters=%s",
        task.pk,
        getattr(task, "execution_id", None),
        strategy_config.get("strategy_type"),
        strategy_config.get("name"),
        _hash_json(strategy_config),
        monitored,
    )


def _get_snapshot(*, task: Any, task_type: str) -> TaskExecutionSnapshot | None:
    execution_id = getattr(task, "execution_id", None)
    if execution_id is None:
        return None
    return (
        TaskExecutionSnapshot.objects.filter(
            task_type=task_type,
            task_id=task.pk,
            execution_id=execution_id,
        )
        .only("task_config", "strategy_config")
        .first()
    )


def _safe_task_snapshot(task: Any) -> dict[str, Any]:
    try:
        return _snapshot_task_config(task)
    except (TypeError, ValueError):
        return {}


def _safe_strategy_snapshot(task: Any) -> dict[str, Any]:
    try:
        return _snapshot_strategy_config(task)
    except (TypeError, ValueError):
        return {}


def _audit(
    *,
    task_changes: dict[str, dict[str, Any]],
    parameter_changes: dict[str, dict[str, Any]],
    current_strategy_config: dict[str, Any],
) -> ResumeConfigAudit:
    parameters = dict(current_strategy_config.get("parameters") or {})
    return ResumeConfigAudit(
        task_changes=task_changes,
        parameter_changes=parameter_changes,
        effective_parameters=parameters,
        strategy_type=current_strategy_config.get("strategy_type"),
        config_name=current_strategy_config.get("name"),
        config_hash=_hash_json(current_strategy_config),
    )


def _initial_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    initial = config.get("initial")
    if isinstance(initial, dict):
        return initial
    return {
        key: value
        for key, value in config.items()
        if key not in {"initial", "current", "revisions", "config_hash"}
    }


def _current_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    current = config.get("current")
    if isinstance(current, dict):
        return current
    return _initial_config(config)


def _with_config_metadata(config: dict[str, Any]) -> dict[str, Any]:
    json_safe = _make_json_safe(config)
    return {
        **json_safe,
        "initial": json_safe,
        "current": json_safe,
        "revisions": [],
        "config_hash": _hash_json(json_safe),
        "segment_index": 1,
    }


def _merge_config_revision(previous: Any, current: dict[str, Any]) -> dict[str, Any]:
    current_safe = _make_json_safe(current)
    if not isinstance(previous, dict) or not previous:
        return _with_config_metadata(current_safe)

    initial = _initial_config(previous)
    previous_current = previous.get("current")
    if not isinstance(previous_current, dict):
        previous_current = _initial_config(previous)

    revisions = previous.get("revisions")
    if not isinstance(revisions, list):
        revisions = []

    if _normalize_for_compare(previous_current) != _normalize_for_compare(current_safe):
        revisions = [
            *revisions,
            {
                "from_hash": _hash_json(previous_current),
                "to_hash": _hash_json(current_safe),
                "changed_fields": sorted(_diff_dict(previous_current, current_safe)),
            },
        ]

    return {
        **current_safe,
        "initial": initial,
        "current": current_safe,
        "revisions": revisions,
        "config_hash": _hash_json(current_safe),
        "segment_index": len(revisions) + 1,
    }


def _diff_dict(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(previous) | set(current)):
        old = previous.get(key)
        new = current.get(key)
        if _normalize_for_compare(old) != _normalize_for_compare(new):
            diff[key] = {"previous": old, "current": new}
    return diff


def _validate_strategy_resume_parameter_compatibility(
    *,
    strategy_type: str | None,
    previous_params: dict[str, Any],
    current_params: dict[str, Any],
) -> None:
    if not strategy_type:
        return
    from apps.trading.strategies.registry import registry

    if not registry.is_registered(strategy_type):
        return

    registry.validate_resume_parameter_compatibility(
        identifier=strategy_type,
        previous_params=previous_params,
        current_params=current_params,
    )


def _hash_json(value: Any) -> str:
    normalized = json.dumps(_normalize_for_compare(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _normalize_for_compare(value: Any) -> Any:
    return json.loads(json.dumps(_make_json_safe(value), sort_keys=True))
