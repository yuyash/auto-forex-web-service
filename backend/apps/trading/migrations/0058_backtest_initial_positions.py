from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0057_tradingtask_live_tick_delivery_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtesttask",
            name="initial_positions_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Create Snowball initial cycles/positions before starting the backtest.",
            ),
        ),
        migrations.AddField(
            model_name="backtesttask",
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
