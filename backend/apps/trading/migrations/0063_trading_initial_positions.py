"""Add initial-position seed settings to trading tasks."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0062_remove_snowball_rebuild_take_profit_recovery"),
    ]

    operations = [
        migrations.AddField(
            model_name="tradingtask",
            name="initial_positions_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Create Snowball initial cycles/positions before starting the trading task."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="initial_position_cycles",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Requested Snowball initial cycle/position structure. "
                    "Positions, trades, orders, and strategy state are generated from this data."
                ),
            ),
        ),
    ]
