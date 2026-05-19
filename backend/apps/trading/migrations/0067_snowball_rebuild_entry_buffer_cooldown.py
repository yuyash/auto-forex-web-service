"""Backfill new Snowball rebuild buffer/cooldown parameters on persisted configs.

Adds ``rebuild_entry_buffer_pips`` and ``rebuild_cooldown_seconds`` (both
default ``0``) to legacy strategy configurations so ``strict_from_dict``
keeps accepting them and the parameter UI exposes the new controls.
"""

from __future__ import annotations

from django.db import migrations
from django.utils import timezone


SNOWBALL_REBUILD_BUFFER_DEFAULTS = {
    "rebuild_entry_buffer_pips": "0",
    "rebuild_cooldown_seconds": "0",
}


def backfill_snowball_rebuild_buffer_cooldown(apps, schema_editor):
    """Insert the new defaults on every persisted snowball config that lacks them."""
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    now = timezone.now()
    for config in StrategyConfiguration.objects.filter(strategy_type="snowball").iterator(
        chunk_size=200
    ):
        if not isinstance(config.parameters, dict):
            continue
        parameters = dict(config.parameters)
        changed = False
        for key, value in SNOWBALL_REBUILD_BUFFER_DEFAULTS.items():
            if key in parameters:
                continue
            parameters[key] = value
            changed = True
        if not changed:
            continue
        config.parameters = parameters
        config.updated_at = now
        config.save(update_fields=["parameters", "updated_at"])


def revert_backfill(apps, schema_editor):
    """Remove the new keys to make the migration symmetric."""
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    now = timezone.now()
    for config in StrategyConfiguration.objects.filter(strategy_type="snowball").iterator(
        chunk_size=200
    ):
        if not isinstance(config.parameters, dict):
            continue
        parameters = dict(config.parameters)
        changed = False
        for key in SNOWBALL_REBUILD_BUFFER_DEFAULTS:
            if key in parameters:
                parameters.pop(key)
                changed = True
        if not changed:
            continue
        config.parameters = parameters
        config.updated_at = now
        config.save(update_fields=["parameters", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0066_metrics_rollup"),
    ]

    operations = [
        migrations.RunPython(
            backfill_snowball_rebuild_buffer_cooldown,
            revert_backfill,
        ),
    ]
