"""Remove obsolete Snowball rebuild take-profit recovery parameters."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import migrations
from django.utils import timezone


OBSOLETE_KEYS = {
    "rebuild_take_profit_recovery_enabled",
    "rebuild_take_profit_recovery_mode",
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


def remove_snowball_take_profit_recovery_parameters(apps, schema_editor):
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    now = timezone.now()
    configs_to_update = []

    for config in StrategyConfiguration.objects.filter(strategy_type="snowball"):
        if not isinstance(config.parameters, dict):
            continue

        parameters = dict(config.parameters)
        changed = False
        for key in OBSOLETE_KEYS:
            if key in parameters:
                parameters.pop(key, None)
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
        ("trading", "0061_tradingtask_display_currency"),
    ]

    operations = [
        migrations.RunPython(
            remove_snowball_take_profit_recovery_parameters,
            migrations.RunPython.noop,
        ),
    ]
