"""Clean obsolete Snowball rebuild, grid-order, and lock parameters."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import migrations
from django.utils import timezone


OBSOLETE_KEYS = {
    "disable_loss_cut_after_rebuild",
    "grid_order_validation_enabled",
    "lock_enabled",
    "n_th",
    "cooldown_sec",
    "rebuild_price_adjustment_enabled",
    "rebuild_entry_price_buffer_pips",
    "rebuild_exit_price_buffer_pips",
    "reseed_on_grid_exhausted",
    "complete_cycle_when_empty",
    "refill_enabled",
}


def _normalize_for_hash(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _runtime_hash(*, strategy_type: str, parameters: dict[str, Any]) -> str:
    payload = {
        "strategy_type": str(strategy_type),
        "parameters": _normalize_for_hash(parameters or {}),
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool_or_default(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return default


def clean_snowball_parameters(apps, schema_editor):
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    now = timezone.now()
    configs_to_update = []

    for config in StrategyConfiguration.objects.filter(strategy_type="snowball"):
        if not isinstance(config.parameters, dict):
            continue

        parameters = dict(config.parameters)
        legacy_refill_enabled = parameters.get("refill_enabled")
        changed = False
        for key in OBSOLETE_KEYS:
            if key in parameters:
                parameters.pop(key, None)
                changed = True

        if "rebuild_entry_price_mode" not in parameters:
            parameters["rebuild_entry_price_mode"] = "original_entry"
            changed = True

        if "refill_limit_enabled" not in parameters:
            parameters["refill_limit_enabled"] = True
            if not _bool_or_default(legacy_refill_enabled, True):
                parameters["refill_up_to"] = 0
            changed = True

        if not changed:
            continue

        config.parameters = parameters
        config.config_hash = _runtime_hash(
            strategy_type=config.strategy_type,
            parameters=parameters,
        )
        config.updated_at = now
        configs_to_update.append(config)

    if configs_to_update:
        StrategyConfiguration.objects.bulk_update(
            configs_to_update,
            ["parameters", "config_hash", "updated_at"],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0064_initial_position_seed_flags"),
    ]

    operations = [
        migrations.RunPython(
            clean_snowball_parameters,
            migrations.RunPython.noop,
        ),
    ]
