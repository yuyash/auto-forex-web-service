"""Remove trading_mode field from BacktestTask and TradingTask.

The trading_mode field was never used by the trading engine.
Hedging/netting behavior is controlled by the strategy configuration's
hedging_enabled parameter and the OANDA account's hedgingEnabled flag.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0027_alter_order_direction"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="backtesttask",
            name="trading_mode",
        ),
        migrations.RemoveField(
            model_name="tradingtask",
            name="trading_mode",
        ),
    ]
