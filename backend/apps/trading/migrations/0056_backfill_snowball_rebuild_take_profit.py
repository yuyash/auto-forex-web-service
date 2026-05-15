from django.db import migrations
from django.utils import timezone


SNOWBALL_REBUILD_TAKE_PROFIT_DEFAULTS = {
    "rebuild_take_profit_mode": "same_pips",
    "rebuild_take_profit_pips_head": "25",
    "rebuild_take_profit_pips_tail": "10",
    "rebuild_take_profit_pips_flat_steps": 0,
    "rebuild_take_profit_pips_gamma": "1.4",
    "rebuild_take_profit_manual_pips": [],
}


def backfill_snowball_rebuild_take_profit_defaults(apps, schema_editor):
    StrategyConfiguration = apps.get_model("trading", "StrategyConfiguration")
    now = timezone.now()
    configs_to_update = []

    for config in StrategyConfiguration.objects.filter(strategy_type="snowball"):
        if not isinstance(config.parameters, dict):
            continue

        parameters = dict(config.parameters)
        changed = False
        for key, value in SNOWBALL_REBUILD_TAKE_PROFIT_DEFAULTS.items():
            if key in parameters:
                continue
            parameters[key] = list(value) if isinstance(value, list) else value
            changed = True

        if not changed:
            continue

        config.parameters = parameters
        config.updated_at = now
        configs_to_update.append(config)

    if configs_to_update:
        StrategyConfiguration.objects.bulk_update(
            configs_to_update,
            ["parameters", "updated_at"],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0055_alter_position_layer_index_alter_trade_layer_index"),
    ]

    operations = [
        migrations.RunPython(
            backfill_snowball_rebuild_take_profit_defaults,
            migrations.RunPython.noop,
        ),
    ]
