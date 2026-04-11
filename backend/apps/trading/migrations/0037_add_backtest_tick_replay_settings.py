from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0036_add_stop_loss_price_to_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtesttask",
            name="tick_granularity",
            field=models.CharField(
                choices=[
                    ("tick", "All Ticks"),
                    ("1s", "1 Second"),
                    ("10s", "10 Seconds"),
                    ("15s", "15 Seconds"),
                    ("30s", "30 Seconds"),
                    ("1m", "1 Minute"),
                    ("5m", "5 Minutes"),
                    ("15m", "15 Minutes"),
                    ("30m", "30 Minutes"),
                    ("1h", "1 Hour"),
                ],
                default="tick",
                help_text="Tick replay granularity for backtests. Use 'tick' for full tick-by-tick replay, or a time bucket such as '1s' or '1m'.",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="backtesttask",
            name="tick_window_value_mode",
            field=models.CharField(
                choices=[
                    ("first", "First Tick"),
                    ("last", "Last Tick"),
                    ("average", "Average"),
                    ("median", "Median"),
                ],
                default="last",
                help_text="Representative value to use when replay granularity is aggregated. Ignored when tick_granularity='tick'.",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="backtesttask",
            index=models.Index(
                fields=["instrument", "tick_granularity", "tick_window_value_mode"],
                name="backtest_ta_instrum_e42678_idx",
            ),
        ),
    ]
