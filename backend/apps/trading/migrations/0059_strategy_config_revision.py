"""Add StrategyConfiguration revision metadata."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import migrations, models


def _normalize(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _runtime_hash(*, strategy_type: str, parameters: dict[str, Any]) -> str:
    payload = {
        "strategy_type": str(strategy_type or ""),
        "parameters": _normalize(parameters or {}),
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _current_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    current = config.get("current")
    if isinstance(current, dict):
        return dict(current)
    initial = config.get("initial")
    if isinstance(initial, dict):
        return dict(initial)
    return {
        key: value
        for key, value in config.items()
        if key not in {"initial", "current", "revisions", "config_hash", "segment_index"}
    }


def _snapshot_config_id(config: dict[str, Any], current: dict[str, Any]) -> str:
    return str(current.get("id") or config.get("id") or "")


def _assign_snapshot_revision(
    *,
    strategy_config: dict[str, Any],
    revision: int,
    runtime_hash: str,
) -> dict[str, Any]:
    enriched = dict(strategy_config)
    enriched["configuration_revision"] = revision
    enriched["configuration_hash"] = runtime_hash

    current = enriched.get("current")
    if isinstance(current, dict):
        enriched["current"] = {
            **current,
            "configuration_revision": revision,
            "configuration_hash": runtime_hash,
        }
    else:
        base_current = _current_config(enriched)
        if base_current:
            enriched["current"] = {
                **base_current,
                "configuration_revision": revision,
                "configuration_hash": runtime_hash,
            }
    return enriched


def _assign_revision(
    revision_state: dict[str, dict[str, Any]], config_id: str, runtime_hash: str
) -> int:
    state = revision_state.setdefault(
        config_id,
        {
            "revision": 0,
            "hash": None,
        },
    )
    if state["revision"] == 0:
        state["revision"] = 1
    elif state["hash"] != runtime_hash:
        state["revision"] += 1
    state["hash"] = runtime_hash
    return int(state["revision"])


def forwards(apps, schema_editor) -> None:
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    TaskExecutionSnapshot = apps.get_model("trading", "TaskExecutionSnapshot")

    revision_state: dict[str, dict[str, Any]] = {}

    snapshots = TaskExecutionSnapshot.objects.exclude(strategy_config={}).order_by(
        "created_at", "id"
    )
    for snapshot in snapshots.iterator():
        strategy_config = snapshot.strategy_config or {}
        if not isinstance(strategy_config, dict):
            continue
        current = _current_config(strategy_config)
        config_id = _snapshot_config_id(strategy_config, current)
        if not config_id:
            continue
        strategy_type = str(
            current.get("strategy_type") or strategy_config.get("strategy_type") or ""
        )
        parameters = current.get("parameters")
        runtime_hash = _runtime_hash(
            strategy_type=strategy_type,
            parameters=parameters if isinstance(parameters, dict) else {},
        )
        revision = _assign_revision(revision_state, config_id, runtime_hash)
        snapshot.strategy_config = _assign_snapshot_revision(
            strategy_config=strategy_config,
            revision=revision,
            runtime_hash=runtime_hash,
        )
        snapshot.save(update_fields=["strategy_config"])

    for config in StrategyConfiguration.objects.order_by("created_at", "id").iterator():
        runtime_hash = _runtime_hash(
            strategy_type=config.strategy_type,
            parameters=config.parameters if isinstance(config.parameters, dict) else {},
        )
        config.revision = _assign_revision(revision_state, str(config.pk), runtime_hash)
        config.config_hash = runtime_hash
        config.save(update_fields=["revision", "config_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0058_backtest_initial_positions"),
    ]

    operations = [
        migrations.AddField(
            model_name="strategyconfiguration",
            name="revision",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Monotonic revision for runtime-affecting configuration changes",
            ),
        ),
        migrations.AddField(
            model_name="strategyconfiguration",
            name="config_hash",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Stable hash of strategy_type and parameters for this revision",
                max_length=64,
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
