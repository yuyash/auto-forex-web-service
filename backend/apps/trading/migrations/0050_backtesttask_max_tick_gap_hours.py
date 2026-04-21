"""Add configurable tick-gap threshold to backtest tasks."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0049_add_backtest_market_close_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtesttask",
            name="max_tick_gap_hours",
            field=models.PositiveIntegerField(
                default=120,
                help_text=(
                    "Maximum forward gap between replayed ticks, in hours, before the "
                    "backtest is failed as suspicious. Default: 120 (5 days)."
                ),
            ),
        ),
    ]
