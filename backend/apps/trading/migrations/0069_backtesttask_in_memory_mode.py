from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0068_backtest_holiday_calendar"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtesttask",
            name="in_memory_mode",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Run the backtest with in-memory execution records. "
                    "Orders, positions, trades, and strategy events are not persisted; "
                    "only task state, metrics, and terminal snapshots are stored."
                ),
            ),
        ),
    ]
